# -*- coding: utf-8 -*-
# Copyright 2013-2016 Hewlett Packard Enterprise Development LP
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
Eucalyptus and AWS ELB constants

"""
from ..i18n import _


ELB_BACKEND_CERTIFICATE_NAME_PREFIX = 'EucaConsole-BackendServerAuthPolicy'
ELB_PREDEFINED_SECURITY_POLICY_NAME_PREFIX = 'ELBSecurityPolicy'
ELB_CUSTOM_SECURITY_POLICY_NAME_PREFIX = 'ELB-CustomSecurityPolicy'

ELB_EMPTY_DATA_MESSAGE = _("No data available until this load balancer receives traffic.")
ELB_EMPTY_HOSTS_MESSAGE = _("No data available until instances are registered with this load balancer.")

ELB_MONITORING_CHARTS_LIST = [
    {
        'metric': 'RequestCount',
        'unit': 'Count',
        'statistic': 'Sum',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _(
            'The total number of completed requests that were received and routed to the registered instances. '
            'Defaults to the sum statistic for the best output results.'),
    },
    {
        'metric': 'Latency',
        'unit': 'Seconds',
        'statistic': 'Average',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _(
            'The average elapsed time (in milliseconds) between a request from the load balancer and when a '
            'response is received. Defaults to the average statistic for the best output results.'),
    },
    {
        'metric': 'UnHealthyHostCount',
        'unit': 'Count',
        'statistic': 'Maximum',
        'empty_msg': ELB_EMPTY_HOSTS_MESSAGE,
        'help': _('The number of unhealthy instances in each Availability Zone as it exceeds the unhealthy '
                  'threshold defined for the health checks. If load balancing is enabled across zones, '
                  'the number of unhealthy instances is based on the health criteria across all Availability Zones. '
                  'Uses the maximum statistic for the best output results.'),
    },
    {
        'metric': 'HealthyHostCount',
        'unit': 'Count',
        'statistic': 'Maximum',
        'empty_msg': ELB_EMPTY_HOSTS_MESSAGE,
        'help': _('The number of healthy instances in each Availability Zone as defined by the healthy threshold. '
                  'If load balancing is enabled across zones, the number of healthy instances is based on the health '
                  'criteria across all Availability Zones. Uses the maximum statistic for the best output results.'),
    },
    {
        'metric': 'HTTPCode_ELB_4XX',
        'unit': 'Count',
        'statistic': 'Sum',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _(' When the listener is configured to use HTTP or HTTPS protocols, this metric represents the number '
                  'of HTTP 4XX client error codes generated by the load balancer when a request is malformed or '
                  'incomplete. Defaults to the sum statistic for the best output results.'),
    },
    {
        'metric': 'HTTPCode_ELB_5XX',
        'unit': 'Count',
        'statistic': 'Sum',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _('When the listener is configured to use HTTP or HTTPS protocols, this metric represents the number '
                  'of HTTP 5XX server error codes generated by the load balancer if there are no healthy instances '
                  'registered, or if the request rate exceeds the capacity of the instances or the load balancer. '
                  'Defaults to the sum statistic for the best output results.'),
    },
    {
        'metric': 'HTTPCode_Backend_2XX',
        'unit': 'Count',
        'statistic': 'Sum',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _('The number of HTTP response codes generated by registered instances but not by the load balancer. '
                  'Defaults to the sum statistic for the best output results.'),
    },
    {
        'metric': 'HTTPCode_Backend_3XX',
        'unit': 'Count',
        'statistic': 'Sum',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _('The number of HTTP response codes generated by registered instances but not by the load balancer. '
                  'Defaults to the sum statistic for the best output results.'),
    },
    {
        'metric': 'HTTPCode_Backend_4XX',
        'unit': 'Count',
        'statistic': 'Sum',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _('The number of HTTP response codes generated by registered instances but not by the load balancer. '
                  'Defaults to the sum statistic for the best output results.'),
    },
    {
        'metric': 'HTTPCode_Backend_5XX',
        'unit': 'Count',
        'statistic': 'Sum',
        'empty_msg': ELB_EMPTY_DATA_MESSAGE,
        'help': _('The number of HTTP response codes generated by registered instances but not by the load balancer. '
                  'Defaults to the sum statistic for the best output results.'),
    },
]


SSL_CIPHERS = [
    'ECDHE-ECDSA-AES128-GCM-SHA256',
    'ECDHE-RSA-AES128-GCM-SHA256',
    'ECDHE-ECDSA-AES128-SHA256',
    'ECDHE-RSA-AES128-SHA256',
    'ECDHE-ECDSA-AES128-SHA',
    'ECDHE-RSA-AES128-SHA',
    'DHE-RSA-AES128-SHA',
    'ECDHE-ECDSA-AES256-GCM-SHA384',
    'ECDHE-RSA-AES256-GCM-SHA384',
    'ECDHE-ECDSA-AES256-SHA384',
    'ECDHE-RSA-AES256-SHA384',
    'ECDHE-RSA-AES256-SHA',
    'ECDHE-ECDSA-AES256-SHA',
    'AES128-GCM-SHA256',
    'AES128-SHA256',
    'AES128-SHA',
    'AES256-GCM-SHA384',
    'AES256-SHA256',
    'AES256-SHA',
    'DHE-DSS-AES128-SHA',
    'CAMELLIA128-SHA',
    'EDH-RSA-DES-CBC3-SHA',
    'DES-CBC3-SHA',
    'DHE-DSS-AES256-GCM-SHA384',
    'DHE-RSA-AES256-GCM-SHA384',
    'DHE-RSA-AES256-SHA256',
    'DHE-DSS-AES256-SHA256',
    'DHE-RSA-AES256-SHA',
    'DHE-DSS-AES256-SHA',
    'DHE-RSA-CAMELLIA256-SHA',
    'DHE-DSS-CAMELLIA256-SHA',
    'CAMELLIA256-SHA',
    'EDH-DSS-DES-CBC3-SHA',
    'DHE-DSS-AES128-GCM-SHA256',
    'DHE-RSA-AES128-GCM-SHA256',
    'DHE-RSA-AES128-SHA256',
    'DHE-DSS-AES128-SHA256',
    'DHE-RSA-CAMELLIA128-SHA',
    'DHE-DSS-CAMELLIA128-SHA',
    'ADH-AES128-GCM-SHA256',
    'ADH-AES128-SHA',
    'ADH-AES128-SHA256',
    'ADH-AES256-GCM-SHA384',
    'ADH-AES256-SHA',
    'ADH-AES256-SHA256',
    'ADH-CAMELLIA128-SHA',
    'ADH-CAMELLIA256-SHA',
    'ADH-DES-CBC3-SHA',
    'ADH-DES-CBC-SHA',
    'ADH-SEED-SHA',
    'DES-CBC-SHA',
    'DHE-DSS-SEED-SHA',
    'DHE-RSA-SEED-SHA',
    'EDH-DSS-DES-CBC-SHA',
    'EDH-RSA-DES-CBC-SHA',
    'IDEA-CBC-SHA',
    'SEED-SHA',
    'DES-CBC3-MD5',
    'DES-CBC-MD5',
]

# Mapping of ELB account ID by AWS region (used for setting ACLs on ELB access logs)
# See http://docs.aws.amazon.com/ElasticLoadBalancing/latest/DeveloperGuide/enable-access-logs.html
AWS_ELB_ACCOUNT_IDS = {
    'us-east-1': '127311923021',
    'us-west-1': '027434742980',
    'us-west-2': '797873946194',
    'eu-west-1': '156460612806',
    'eu-central-1': '054676820928',
    'ap-northeast-1': '582318560864',
    'ap-southeast-1': '114774131450',
    'ap-southeast-2': '783225319266',
    'sa-east-1': '507241528517',
    'us-gov-west-1': '048591011584',
    'cn-north-1': '638102146993',
}
