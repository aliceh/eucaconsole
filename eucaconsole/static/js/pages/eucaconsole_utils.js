/**
 * @fileOverview Common JS for Eucalyptus Management Console
 * @requires AngularJS
 *
 */

angular.module('EucaConsoleUtils', [])
.service('eucaUnescapeJson', function() {
    /**
     * Unescape JSON escaped server-side via BaseView.escape_json() custom method
     * @param {string} jsonString - JSON string, with single/double quotes and backslashes escaped.
     * @return {string} unescaped JSON string
     */
    return function(jsonString) {
        return jsonString.replace(/__apos__/g, "\'").replace(/__dquote__/g, '\\"').replace(/__bslash__/g, "\\");
    };
});


