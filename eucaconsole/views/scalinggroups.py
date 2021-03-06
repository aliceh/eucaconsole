# -*- coding: utf-8 -*-
# Copyright 2013-2014 Eucalyptus Systems, Inc.
#
# Redistribution and use of this software in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Pyramid views for Eucalyptus and AWS scaling groups

"""
import simplejson as json
import time

from hashlib import md5
from markupsafe import escape
from operator import attrgetter

from boto.ec2.autoscale import AutoScalingGroup, ScalingPolicy
from boto.ec2.autoscale.tag import Tag

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ..constants.cloudwatch import METRIC_TYPES
from ..forms.alarms import CloudWatchAlarmCreateForm
from ..forms.scalinggroups import (
    ScalingGroupDeleteForm, ScalingGroupEditForm,
    ScalingGroupCreateForm, ScalingGroupInstancesMarkUnhealthyForm,
    ScalingGroupInstancesTerminateForm, ScalingGroupPolicyCreateForm,
    ScalingGroupPolicyDeleteForm, ScalingGroupsFiltersForm)
from ..i18n import _
from ..models import Notification
from ..views import LandingPageView, BaseView, TaggedItemView, JSONResponse
from . import boto_error_handler


class DeleteScalingGroupMixin(object):
    def wait_for_instances_to_shutdown(self, scaling_group):
        if scaling_group.instances:
            ec2_conn = self.get_connection()
            instance_ids = [i.instance_id for i in scaling_group.instances]
            is_all_shutdown = False
            count = 0
            while is_all_shutdown is False and count < 30:
                instances = ec2_conn.get_only_instances(instance_ids)
                if instances:
                    is_all_shutdown = True
                    for instance in instances:
                        if self.cloud_type == 'aws':
                            if not str(instance._state).startswith('terminated'):
                                is_all_shutdown = False
                        else:
                            if not str(instance._state).startswith('terminated') and not str(instance._state).startswith('shutting-down'):
                                is_all_shutdown = False
                    time.sleep(5)
                count += 1
        return


class ScalingGroupsView(LandingPageView, DeleteScalingGroupMixin):
    TEMPLATE = '../templates/scalinggroups/scalinggroups.pt'

    def __init__(self, request):
        super(ScalingGroupsView, self).__init__(request)
        self.initial_sort_key = 'name'
        self.prefix = '/scalinggroups'
        self.delete_form = ScalingGroupDeleteForm(self.request, formdata=self.request.params or None)
        self.json_items_endpoint = self.get_json_endpoint('scalinggroups_json')
        self.ec2_conn = self.get_connection()
        self.autoscale_conn = self.get_connection(conn_type='autoscale')
        self.vpc_conn = self.get_connection(conn_type='vpc')
        self.filters_form = ScalingGroupsFiltersForm(
            self.request, formdata=self.request.params or None,
            ec2_conn=self.ec2_conn, autoscale_conn=self.autoscale_conn, vpc_conn=self.vpc_conn)
        self.filter_keys = [
            'availability_zones', 'launch_config', 'name', 'placement_group', 'vpc_zone_identifier']
        # sort_keys are passed to sorting drop-down
        self.is_vpc_supported = BaseView.is_vpc_supported(request)
        if not self.is_vpc_supported:
            del self.filters_form.vpc_zone_identifier
        self.render_dict = dict(
            filter_fields=True,
            filters_form=self.filters_form,
            filter_keys=self.filter_keys,
            sort_keys=self.get_sort_keys(),
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
            json_items_endpoint=self.json_items_endpoint,
            delete_form=self.delete_form,
        )

    @view_config(route_name='scalinggroups', renderer=TEMPLATE, request_method='GET')
    def scalinggroups_landing(self):
        return self.render_dict

    @view_config(route_name='scalinggroups_delete', request_method='POST', renderer=TEMPLATE)
    def scalinggroups_delete(self):
        if self.delete_form.validate():
            location = self.request.route_path('scalinggroups')
            name = self.request.params.get('name')
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Deleting scaling group {0}").format(name))
                conn = self.get_connection(conn_type='autoscale')
                scaling_group = self.get_scaling_group_by_name(name)
                # Need to shut down instances prior to scaling group deletion
                scaling_group.shutdown_instances()
                self.wait_for_instances_to_shutdown(scaling_group)
                conn.delete_auto_scaling_group(name)
                prefix = _(u'Successfully deleted scaling group')
                msg = '{0} {1}'.format(prefix, name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.delete_form.get_errors_list()
        return self.render_dict

    def get_scaling_group_by_name(self, name):
        names = [name]
        scaling_groups = self.autoscale_conn.get_all_groups(names) if self.autoscale_conn else []
        if scaling_groups:
            return scaling_groups[0]
        return [] 

    @staticmethod
    def get_sort_keys():
        return [
            dict(key='name', name=_(u'Name: A to Z')),
            dict(key='-name', name=_(u'Name: Z to A')),
            dict(key='-status', name=_(u'Health status')),
            dict(key='-current_instances_count', name=_(u'Current instances')),
            dict(key='launch_config', name=_(u'Launch configuration')),
            dict(key='availability_zones', name=_(u'Availability zones')),
        ]


class ScalingGroupsJsonView(LandingPageView):
    @view_config(route_name='scalinggroups_json', renderer='json', request_method='POST')
    def scalinggroups_json(self):
        if not(self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        scalinggroups = []
        with boto_error_handler(self.request):
            items = self.filter_items(
                self.get_items(), ignore=['availability_zones', 'vpc_zone_identifier'],  autoscale=True)
            if self.request.params.getall('availability_zones'):
                items = self.filter_by_availability_zones(items)
            if self.request.params.getall('vpc_zone_identifier'):
                items = self.filter_by_vpc_zone_identifier(items)
        for group in items:
            group_instances = group.instances or []
            all_healthy = all(instance.health_status == 'Healthy' for instance in group_instances)
            scalinggroups.append(dict(
                availability_zones=', '.join(sorted(group.availability_zones)),
                load_balancers=', '.join(sorted(group.load_balancers)),
                desired_capacity=group.desired_capacity,
                launch_config=group.launch_config_name,
                max_size=group.max_size,
                min_size=group.min_size,
                name=group.name,
                placement_group=group.placement_group,
                termination_policies=', '.join(group.termination_policies),
                current_instances_count=len(group_instances),
                status='Healthy' if all_healthy else 'Unhealthy',
            ))
        return dict(results=scalinggroups)

    def get_items(self):
        conn = self.get_connection(conn_type='autoscale')
        return conn.get_all_groups() if conn else []

    def filter_by_availability_zones(self, items):
        filtered_items = []
        for item in items:
            isMatched = False
            for zone in self.request.params.getall('availability_zones'):
                for selected_zone in item.availability_zones:
                    if selected_zone == zone:
                        isMatched = True
            if isMatched:
                filtered_items.append(item)
        return filtered_items

    def filter_by_vpc_zone_identifier(self, items):
        filtered_items = []
        for item in items:
            isMatched = False
            for vpc_zone in self.request.params.getall('vpc_zone_identifier'):
                if item.vpc_zone_identifier is None or item.vpc_zone_identifier == '':
                    # Handle the 'No subnets' Case
                    if vpc_zone == 'None':
                        isMatched = True
                elif item.vpc_zone_identifier and item.vpc_zone_identifier.find(vpc_zone) != -1:
                    isMatched = True
            if isMatched:
                filtered_items.append(item)
        return filtered_items


class BaseScalingGroupView(BaseView):
    def __init__(self, request):
        super(BaseScalingGroupView, self).__init__(request)
        self.autoscale_conn = self.get_connection(conn_type='autoscale')
        self.cloudwatch_conn = self.get_connection(conn_type='cloudwatch')
        self.elb_conn = self.get_connection(conn_type='elb')
        self.vpc_conn = self.get_connection(conn_type='vpc')
        self.ec2_conn = self.get_connection()
        self.is_vpc_supported = BaseView.is_vpc_supported(request)

    def get_scaling_group(self):
        scalinggroup_param = self.request.matchdict.get('id')  # id = scaling_group.name
        scalinggroups_param = [scalinggroup_param]
        scaling_groups = []
        if self.autoscale_conn:
            scaling_groups = self.autoscale_conn.get_all_groups(names=scalinggroups_param)
        return scaling_groups[0] if scaling_groups else None

    def get_alarms(self):
        if self.cloudwatch_conn:
            return self.cloudwatch_conn.describe_alarms()
        return []

    def get_policies(self, scaling_group):
        policies = []
        if self.autoscale_conn:
            policies = self.autoscale_conn.get_all_policies(as_group=scaling_group.name)
        return sorted(policies)

    def parse_tags_param(self, scaling_group_name=None):
        tags_json = self.request.params.get('tags')
        tags_list = json.loads(tags_json) if tags_json else []
        tags = []
        for tag in tags_list:
            tags.append(Tag(
                resource_id=scaling_group_name,
                key=self.unescape_braces(tag.get('name', '').strip()),
                value=self.unescape_braces(tag.get('value', '').strip()),
                propagate_at_launch=tag.get('propagate_at_launch', False),
            ))
        return tags


class ScalingGroupView(BaseScalingGroupView, DeleteScalingGroupMixin):
    """Views for Scaling Group detail page"""
    TEMPLATE = '../templates/scalinggroups/scalinggroup_view.pt'

    def __init__(self, request):
        super(ScalingGroupView, self).__init__(request)
        with boto_error_handler(request):
            self.scaling_group = self.get_scaling_group()
            self.policies = self.get_policies(self.scaling_group)
            self.vpc = self.get_vpc(self.scaling_group)
            self.vpc_name = TaggedItemView.get_display_name(self.vpc) if self.vpc else ''
        self.edit_form = ScalingGroupEditForm(
            self.request, scaling_group=self.scaling_group, autoscale_conn=self.autoscale_conn, ec2_conn=self.ec2_conn,
            vpc_conn=self.vpc_conn, elb_conn=self.elb_conn, formdata=self.request.params or None)
        self.delete_form = ScalingGroupDeleteForm(self.request, formdata=self.request.params or None)
        self.is_vpc_supported = BaseView.is_vpc_supported(request)
        self.render_dict = dict(
            scaling_group=self.scaling_group,
            scaling_group_name=self.escape_braces(self.scaling_group.name) if self.scaling_group else '',
            vpc_network=self.vpc_name,
            policies=self.policies,
            edit_form=self.edit_form,
            delete_form=self.delete_form,
            avail_zone_placeholder_text=_(u'Select one or more availability zones...'),
            termination_policies_placeholder_text=_(u'Select one or more termination policies...'),
            controller_options_json=self.get_controller_options_json(),
            is_vpc_supported=self.is_vpc_supported,
        )

    @view_config(route_name='scalinggroup_view', renderer=TEMPLATE)
    def scalinggroup_view(self):
        return self.render_dict

    @view_config(route_name='scalinggroup_update', request_method='POST', renderer=TEMPLATE)
    def scalinggroup_update(self):
        if not self.is_vpc_supported or self.request.params.get('vpc_network') is None:
            del self.edit_form.vpc_network
            del self.edit_form.vpc_subnet
        if self.edit_form.validate():
            location = self.request.route_path('scalinggroup_view', id=self.scaling_group.name)
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Updating scaling group {0}").format(self.scaling_group.name))
                self.update_tags()
                self.update_properties()
                prefix = _(u'Successfully updated scaling group')
                msg = '{0} {1}'.format(prefix, self.scaling_group.name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.edit_form.get_errors_list()
        return self.render_dict

    @view_config(route_name='scalinggroup_delete', request_method='POST', renderer=TEMPLATE)
    def scalinggroup_delete(self):
        if self.delete_form.validate():
            location = self.request.route_path('scalinggroups')
            name = self.unescape_braces(self.request.params.get('name'))
            with boto_error_handler(self.request, location):
                # Need to shut down instances prior to scaling group deletion
                self.log_request(_(u"Terminating scaling group {0} instances").format(name))
                self.scaling_group.shutdown_instances()
                self.wait_for_instances_to_shutdown(self.scaling_group)
                self.log_request(_(u"Deleting scaling group {0}").format(name))
                self.autoscale_conn.delete_auto_scaling_group(name)
                prefix = _(u'Successfully deleted scaling group')
                msg = '{0} {1}'.format(prefix, name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.delete_form.get_errors_list()
        return self.render_dict

    def update_tags(self):
        updated_tags_list = self.parse_tags_param(scaling_group_name=self.scaling_group.name)
        # Delete existing tags first
        if self.scaling_group.tags:
            self.autoscale_conn.delete_tags(self.scaling_group.tags)
        if updated_tags_list:
            self.autoscale_conn.create_or_update_tags(updated_tags_list)

    def update_properties(self):
        self.scaling_group.desired_capacity = self.request.params.get('desired_capacity', 1)
        self.scaling_group.launch_config_name = self.unescape_braces(self.request.params.get('launch_config'))
        vpc_subnets = self.request.params.getall('vpc_subnet')
        if vpc_subnets and vpc_subnets[0] != 'None':
            self.scaling_group.vpc_zone_identifier = ','.join(
                [str(x) for x in vpc_subnets]
            )
        # If VPC subnet exists, do not specify availability zones; the API will figure them out based on the VPC subnets
        if not self.scaling_group.vpc_zone_identifier:
            self.scaling_group.availability_zones = self.request.params.getall('availability_zones')
        else:
            self.scaling_group.availability_zones = ''
        self.scaling_group.termination_policies = self.request.params.getall('termination_policies')
        # on AWS, the option 'Default' must appear at the end of the list
        if 'Default' in self.scaling_group.termination_policies:
            self.scaling_group.termination_policies.remove('Default')
            self.scaling_group.termination_policies.append('Default')
        self.scaling_group.max_size = self.request.params.get('max_size', 1)
        self.scaling_group.min_size = self.request.params.get('min_size', 0)
        self.scaling_group.health_check_type = self.request.params.get('health_check_type')
        self.scaling_group.health_check_period = self.request.params.get('health_check_period', 120)
        self.scaling_group.default_cooldown = self.request.params.get('default_cooldown', 120)
        self.scaling_group.update()

    def get_vpc(self, scaling_group):
        with boto_error_handler(self.request):
            if self.vpc_conn and scaling_group.vpc_zone_identifier:
                vpc_subnets = scaling_group.vpc_zone_identifier.split(',')
                vpc_subnet = self.vpc_conn.get_all_subnets(subnet_ids=vpc_subnets[0])
                if vpc_subnet:
                    this_subnet = vpc_subnet[0]
                    if this_subnet and this_subnet.vpc_id:
                        this_vpc = self.vpc_conn.get_all_vpcs(vpc_ids=[this_subnet.vpc_id])
                        if this_vpc:
                            return this_vpc[0]
        return None

    def get_controller_options_json(self):
        if self.scaling_group is None:
            return '{}'
        return BaseView.escape_json(json.dumps({
            'scaling_group_name': self.scaling_group.name,
            'policies_count': len(self.policies),
        }))


class ScalingGroupInstancesView(BaseScalingGroupView):
    """View for Scaling Group Manage Instances page"""
    TEMPLATE = '../templates/scalinggroups/scalinggroup_instances.pt'

    def __init__(self, request):
        super(ScalingGroupInstancesView, self).__init__(request)
        self.scaling_group = self.get_scaling_group()
        self.policies = self.get_policies(self.scaling_group)
        self.markunhealthy_form = ScalingGroupInstancesMarkUnhealthyForm(
            self.request, formdata=self.request.params or None)
        self.terminate_form = ScalingGroupInstancesTerminateForm(self.request, formdata=self.request.params or None)
        self.render_dict = dict(
            scaling_group=self.scaling_group,
            scaling_group_name=self.escape_braces(self.scaling_group.name),
            policies=self.policies,
            markunhealthy_form=self.markunhealthy_form,
            terminate_form=self.terminate_form,
            json_items_endpoint=self.request.route_path('scalinggroup_instances_json', id=self.scaling_group.name),
        )

    @view_config(route_name='scalinggroup_instances', renderer=TEMPLATE, request_method='GET')
    def scalinggroup_instances(self):
        return self.render_dict

    @view_config(route_name='scalinggroup_instances_markunhealthy', renderer=TEMPLATE, request_method='POST')
    def scalinggroup_instances_markunhealthy(self):
        location = self.request.route_path('scalinggroup_instances', id=self.scaling_group.name)
        if self.markunhealthy_form.validate():
            instance_id = self.request.params.get('instance_id')
            respect_grace_period = self.request.params.get('respect_grace_period') == 'y'
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Marking instance {0} unhealthy").format(instance_id))
                self.autoscale_conn.set_instance_health(
                    instance_id, 'Unhealthy', should_respect_grace_period=respect_grace_period)
                prefix = _(u'Successfully marked the following instance as unhealthy:')
                msg = '{0} {1}'.format(prefix, instance_id)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.markunhealthy_form.get_errors_list()
        return self.render_dict

    @view_config(route_name='scalinggroup_instances_terminate', renderer=TEMPLATE, request_method='POST')
    def scalinggroup_instances_terminate(self):
        location = self.request.route_path('scalinggroup_instances', id=self.scaling_group.name)
        if self.terminate_form.validate():
            instance_id = self.request.params.get('instance_id')
            decrement_capacity = self.request.params.get('decrement_capacity') == 'y'
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Terminating scaling group {0} instance {1}").format(
                    self.scaling_group.name, instance_id))
                self.autoscale_conn.terminate_instance(instance_id, decrement_capacity=decrement_capacity)
                prefix = _(u'Successfully sent terminate request for instance')
                msg = '{0} {1}'.format(prefix, instance_id)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.terminate_form.get_errors_list()
        return self.render_dict


class ScalingGroupInstancesJsonView(BaseScalingGroupView):
    """JSON response for Scaling Group Manage Instances page"""

    def __init__(self, request):
        super(ScalingGroupInstancesJsonView, self).__init__(request)
        self.scaling_group = self.get_scaling_group()
        self.ec2_conn = self.get_connection()
        self.instance_objects = self.get_instance_objects()

    @view_config(route_name='scalinggroup_instances_json', renderer='json', request_method='GET')
    def scalinggroup_instances_json(self):
        instances = []
        transitional_states = ['Unhealthy', 'Pending']
        with boto_error_handler(self.request):
            items = self.get_instances()
        for instance in items:
            is_transitional = any([
                instance.lifecycle_state in transitional_states,
                instance.health_status in transitional_states,
            ])
            instances.append(dict(
                id=instance.instance_id,
                name=self.get_display_name(instance.instance_id),
                status=instance.health_status,
                availability_zone=instance.availability_zone,
                launch_config=instance.launch_config_name,
                lifecycle_state=instance.lifecycle_state,
                transitional=is_transitional,
            ))
        return dict(results=instances)

    def get_instances(self):
        if self.scaling_group.instances is None:
            return []
        return sorted(self.scaling_group.instances, key=attrgetter('instance_id'))

    def get_instance_objects(self):
        if self.scaling_group.instances is None:
            return []
        scaling_group_instances_ids = [instance.instance_id for instance in self.scaling_group.instances]
        instances = self.ec2_conn.get_only_instances(instance_ids=scaling_group_instances_ids)
        return sorted(instances, key=attrgetter('id'))

    def get_display_name(self, instance_id):
        matched_instance = [instance for instance in self.instance_objects if instance.id == instance_id]
        instance = matched_instance[0] if matched_instance else None
        if instance is None:
            return instance_id
        return TaggedItemView.get_display_name(instance)


class ScalingGroupPoliciesView(BaseScalingGroupView):
    """View for Scaling Group Policies page"""
    TEMPLATE = '../templates/scalinggroups/scalinggroup_policies.pt'

    def __init__(self, request):
        super(ScalingGroupPoliciesView, self).__init__(request)
        policy_ids = {}
        with boto_error_handler(request):
            self.scaling_group = self.get_scaling_group()
            self.policies = self.get_policies(self.scaling_group)
            for policy in self.policies:
                policy_ids[policy.name] = md5(policy.name).hexdigest()[:8]
            self.alarms = self.get_alarms()
        self.create_form = ScalingGroupPolicyCreateForm(
            self.request, scaling_group=self.scaling_group, alarms=self.alarms, formdata=self.request.params or None)
        self.delete_form = ScalingGroupPolicyDeleteForm(self.request, formdata=self.request.params or None)
        self.render_dict = dict(
            scaling_group=self.scaling_group,
            scaling_group_name=self.escape_braces(self.scaling_group.name),
            create_form=self.create_form,
            delete_form=self.delete_form,
            policies=self.policies,
            policy_ids=policy_ids,
            scale_down_text=_(u'Scale down by'),
            scale_up_text=_(u'Scale up by'),
        )

    @view_config(route_name='scalinggroup_policies', renderer=TEMPLATE, request_method='GET')
    def scalinggroup_policies(self):
        return self.render_dict

    @view_config(route_name='scalinggroup_policy_delete', renderer=TEMPLATE, request_method='POST')
    def scalinggroup_policy_delete(self):
        if self.delete_form.validate():
            location = self.request.route_path('scalinggroup_policies', id=self.scaling_group.name)
            policy_name = self.request.params.get('name')
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Deleting scaling group {0} policy {1}").format(
                    self.scaling_group.name, policy_name))
                self.autoscale_conn.delete_policy(policy_name, autoscale_group=self.scaling_group.name)
                prefix = _(u'Successfully deleted scaling group policy')
                msg = '{0} {1}'.format(prefix, policy_name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.delete_form.get_errors_list()
        return self.render_dict


class ScalingGroupPolicyView(BaseScalingGroupView):
    """View for creating a Scaling Group policy"""
    TEMPLATE = '../templates/scalinggroups/scalinggroup_policy.pt'

    def __init__(self, request):
        super(ScalingGroupPolicyView, self).__init__(request)
        with boto_error_handler(request):
            self.scaling_group = self.get_scaling_group()
            self.alarms = self.get_alarms()
        self.policy_form = ScalingGroupPolicyCreateForm(
            self.request, scaling_group=self.scaling_group, alarms=self.alarms, formdata=self.request.params or None)
        self.alarm_form = CloudWatchAlarmCreateForm(
            self.request, ec2_conn=self.ec2_conn, autoscale_conn=self.autoscale_conn, elb_conn=self.elb_conn,
            scaling_group=self.scaling_group, formdata=self.request.params or None)
        self.render_dict = dict(
            scaling_group=self.scaling_group,
            scaling_group_name=self.escape_braces(self.scaling_group.name),
            alarm_choices=json.dumps(dict(self.policy_form.alarm.choices)),
            policy_form=self.policy_form,
            alarm_form=self.alarm_form,
            create_alarm_redirect=self.request.route_path('scalinggroup_policy_new', id=self.scaling_group.name),
            metric_unit_mapping=json.dumps(self.get_metric_unit_mapping()),
            scale_down_text=_(u'Scale down by'),
            scale_up_text=_(u'Scale up by'),
        )

    @view_config(route_name='scalinggroup_policy_new', renderer=TEMPLATE, request_method='GET')
    def scalinggroup_policy_new(self):
        return self.render_dict

    @view_config(route_name='scalinggroup_policy_create', renderer=TEMPLATE, request_method='POST')
    def scalinggroup_policy_create(self):
        location = self.request.route_path('scalinggroup_policies', id=self.scaling_group.name)
        if self.policy_form.validate():
            adjustment_amount = self.request.params.get('adjustment_amount')
            adjustment_direction = self.request.params.get('adjustment_direction', 'up')
            scaling_adjustment = int(adjustment_amount)
            if adjustment_direction == 'down':
                scaling_adjustment = -scaling_adjustment
            scaling_policy = ScalingPolicy(
                name=self.request.params.get('name'),
                as_name=self.scaling_group.name,
                adjustment_type=self.request.params.get('adjustment_type'),
                scaling_adjustment=scaling_adjustment,
                cooldown=self.request.params.get('cooldown'),
            )
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Creating scaling group {0} policy {1}").format(
                    self.scaling_group.name, scaling_policy.name))
                # Create scaling policy
                self.autoscale_conn.create_scaling_policy(scaling_policy)
                created_scaling_policy = self.autoscale_conn.get_all_policies(
                    as_group=self.scaling_group.name, policy_names=[scaling_policy.name])[0]
                # Attach policy to alarm
                alarm_name = self.request.params.get('alarm')
                alarm = self.cloudwatch_conn.describe_alarms(alarm_names=[alarm_name])[0]
                alarm.dimensions.update({"AutoScalingGroupName": self.scaling_group.name})
                alarm.comparison = alarm._cmp_map.get(alarm.comparison)  # See https://github.com/boto/boto/issues/1311
                # TODO: Detect if an alarm has 5 scaling policies attached to it and abort accordingly
                if created_scaling_policy.policy_arn not in alarm.alarm_actions:
                    alarm.alarm_actions.append(created_scaling_policy.policy_arn)
                alarm.update()
                prefix = _(u'Successfully created scaling group policy')
                msg = '{0} {1}'.format(prefix, scaling_policy.name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.policy_form.get_errors_list()
        return self.render_dict

    @staticmethod
    def get_metric_unit_mapping():
        metric_units = {}
        for mtype in METRIC_TYPES:
            metric_units[mtype.get('name')] = mtype.get('unit')
        return metric_units


class ScalingGroupWizardView(BaseScalingGroupView):
    """View for Create Scaling Group wizard"""
    TEMPLATE = '../templates/scalinggroups/scalinggroup_wizard.pt'

    def __init__(self, request):
        super(ScalingGroupWizardView, self).__init__(request)
        self.request = request
        with boto_error_handler(self.request):
            self.create_form = ScalingGroupCreateForm(
                self.request, autoscale_conn=self.autoscale_conn, ec2_conn=self.ec2_conn,
                vpc_conn=self.vpc_conn, elb_conn=self.elb_conn, formdata=self.request.params or None)
            self.vpc_subnet_choices_json = self.get_vpc_subnets_list()
        self.render_dict = dict(
            create_form=self.create_form,
            launch_config_param=escape(self.request.params.get('launch_config', '')),
            avail_zones_placeholder_text=_(u'Select availability zones...'),
            elb_placeholder_text=_(u'Select load balancers...'),
            vpc_subnet_placeholder_text=_(u'Select VPC subnets...'),
            controller_options_json=self.get_controller_options_json(),
            is_vpc_supported=self.is_vpc_supported,
        )

    def get_controller_options_json(self):
        return BaseView.escape_json(json.dumps({
            'launchconfigs_count': len(self.create_form.launch_config.choices) - 1,  # Ignore blank choice
            'vpc_subnet_choices_json': self.vpc_subnet_choices_json,
            'default_vpc_network': self.get_default_vpc_network(),
        }))

    def get_default_vpc_network(self):
        default_vpc = self.request.session.get('default_vpc', [])
        if self.is_vpc_supported:
            if 'none' in default_vpc or 'None' in default_vpc: 
                if self.cloud_type == 'aws':
                    return 'None'
                # for euca, return the first vpc on the list
                if self.vpc_conn:
                    with boto_error_handler(self.request):
                        vpc_networks = self.vpc_conn.get_all_vpcs()
                        if vpc_networks:
                            return vpc_networks[0].id
            else:
                return default_vpc[0]
        return 'None'

    @view_config(route_name='scalinggroup_new', renderer=TEMPLATE, request_method='GET')
    def scalinggroup_new(self):
        """Displays the Launch Instance wizard"""
        return self.render_dict

    @view_config(route_name='scalinggroup_create', renderer=TEMPLATE, request_method='POST')
    def scalinggroup_create(self):
        """Handles the POST from the Create Scaling Group wizard"""
        if not self.is_vpc_supported:
            del self.create_form.vpc_network
            del self.create_form.vpc_subnet
        if self.create_form.validate():
            with boto_error_handler(self.request, self.request.route_path('scalinggroups')):
                scaling_group_name = self.request.params.get('name')
                self.log_request(_(u"Creating scaling group {0}").format(scaling_group_name))
                launch_config_name = self.unescape_braces(self.request.params.get('launch_config'))
                vpc_network = self.request.params.get('vpc_network') or None
                if vpc_network == 'None':
                    vpc_network = None
                vpc_subnets = self.request.params.getall('vpc_subnet')
                scaling_group = ''
                params = dict(
                    name=scaling_group_name,
                    launch_config=launch_config_name,
                    load_balancers=self.request.params.getall('load_balancers'),
                    health_check_type=self.request.params.get('health_check_type'),
                    health_check_period=self.request.params.get('health_check_period'),
                    desired_capacity=self.request.params.get('desired_capacity'),
                    min_size=self.request.params.get('min_size'),
                    max_size=self.request.params.get('max_size'),
                    tags=self.parse_tags_param(scaling_group_name=scaling_group_name),
                )
                if vpc_network is None:
                    # EC2-Classic case
                    params.update(dict(
                        availability_zones=self.request.params.getall('availability_zones'),
                    ))
                    scaling_group = AutoScalingGroup(**params)
                else:
                    # EC2-VPC case
                    params.update(dict(
                        vpc_zone_identifier=vpc_subnets,
                    ))
                    scaling_group = AutoScalingGroup(**params)

                self.autoscale_conn.create_auto_scaling_group(scaling_group)
                msg = _(u'Successfully created scaling group')
                msg += ' {0}'.format(scaling_group.name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
                location = self.request.route_path('scalinggroup_view', id=scaling_group.name)
                return HTTPFound(location=location)
        else:
            self.request.error_messages = self.create_form.get_errors_list()
        return self.render_dict

    def get_vpc_subnets_list(self):
        subnets = []
        if self.vpc_conn:
            with boto_error_handler(self.request):
                vpc_subnets = self.vpc_conn.get_all_subnets()
                for vpc_subnet in vpc_subnets:
                    subnets.append(dict(
                        id=vpc_subnet.id,
                        vpc_id=vpc_subnet.vpc_id,
                        availability_zone=vpc_subnet.availability_zone,
                        state=vpc_subnet.state,
                        cidr_block=vpc_subnet.cidr_block,
                    ))
        return subnets
