/**
 * @fileOverview Create Scaling Group wizard page JS
 * @requires AngularJS
 *
 */

// Scaling Group wizard includes the AutoScale Tag Editor
angular.module('ScalingGroupWizard', ['AutoScaleTagEditor'])
    .controller('ScalingGroupWizardCtrl', function ($scope) {
        $scope.form = $('#scalinggroup-wizard-form');
        $scope.healthCheckType = 'EC2';
        $scope.healthCheckPeriod = 120;
        $scope.minSize = 1;
        $scope.desiredCapacity = 1;
        $scope.maxSize = 1;
        $scope.urlParams = $.url().param();
        $scope.launchConfig = '';
        $scope.summarySection = $('.summary');
        $scope.currentStepIndex = 1;
        $scope.initChosenSelectors = function () {
            $('#launch_config').chosen({'width': '80%', search_contains: true});
            $('#load_balancers').chosen({'width': '80%', search_contains: true});
            $('#availability_zones').chosen({'width': '100%', search_contains: true});
        };
        $scope.setInitialValues = function () {
            $scope.availZones = $('#availability_zones').val();
        };
        $scope.initController = function (launchConfigCount) {
            $scope.initChosenSelectors();
            $scope.setInitialValues();
            $scope.setWatcher();
            $(document).ready(function () {
                $scope.displayLaunchConfigWarning(launchConfigCount);
            });
        };
        $scope.setWatcher = function (){
            $scope.$watch('currentStepIndex', function(){
                 $scope.setWizardFocus($scope.currentStepIndex);
            });
        }
        $scope.setWizardFocus = function (stepIdx) {
            var modal = $('div').filter("#step" + stepIdx);
            var inputElement = modal.find('input[type!=hidden]').get(0);
            var textareaElement = modal.find('textarea[class!=hidden]').get(0);
            var selectElement = modal.find('select').get(0);
            var modalButton = modal.find('button').get(0);
            if (!!textareaElement){
                textareaElement.focus();
            } else if (!!inputElement) {
                inputElement.focus();
            } else if (!!selectElement) {
                selectElement.focus();
            } else if (!!modalButton) {
                modalButton.focus();
            }
        };
        $scope.visitNextStep = function (nextStep, $event) {
            // Trigger form validation before proceeding to next step
            $scope.form.trigger('validate');
            var currentStep = nextStep - 1,
                tabContent = $scope.form.find('#step' + currentStep),
                invalidFields = tabContent.find('[data-invalid]');
            if (invalidFields.length) {
                invalidFields.focus();
                $event.preventDefault();
                return false;
            }
            // If all is well, click the relevant tab to go to next step
            $('#tabStep' + nextStep).click();
            $scope.currentStepIndex = nextStep;
            // Unhide step 2 of summary
            if (nextStep === 2) {
                $scope.summarySection.find('.step2').removeClass('hide');
            }
        };
        $scope.handleSizeChange = function () {
            // Adjust desired/max based on min size change
            if ($scope.desiredCapacity < $scope.minSize) {
                $scope.desiredCapacity = $scope.minSize;
            }
            if ($scope.maxSize < $scope.desiredCapacity) {
                $scope.maxSize = $scope.desiredCapacity;
            }
        };
        $scope.displayLaunchConfigWarning = function (launchConfigCount) {
            if (launchConfigCount === 0) {
                $('#create-warn-modal').foundation('reveal', 'open');
            }
        };
    })
;

