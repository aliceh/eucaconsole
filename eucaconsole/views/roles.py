# -*- coding: utf-8 -*-
"""
Pyramid views for Eucalyptus and AWS Roles

"""
from datetime import datetime
from dateutil import parser
import simplejson as json
from urllib import urlencode

from boto.exception import BotoServerError
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.i18n import TranslationString as _
from pyramid.view import view_config

from ..forms.roles import RoleForm, RoleUpdateForm, DeleteRoleForm
from ..models import Notification
from ..views import BaseView, LandingPageView, JSONResponse
from . import boto_error_handler


class RolesView(LandingPageView):
    TEMPLATE = '../templates/roles/roles.pt'

    def __init__(self, request):
        super(RolesView, self).__init__(request)
        self.conn = self.get_connection(conn_type="iam")
        self.initial_sort_key = 'role_name'
        self.prefix = '/roles'
        self.delete_form = DeleteRoleForm(self.request, formdata=self.request.params or None)

    @view_config(route_name='roles', renderer=TEMPLATE)
    def roles_landing(self):
        json_items_endpoint = self.request.route_path('roles_json')
        if self.request.GET:
            json_items_endpoint += '?{params}'.format(params=urlencode(self.request.GET))
        user_choices = []  # sorted(set(item.user_name for item in conn.get_all_users().users))
        # filter_keys are passed to client-side filtering in search box
        self.filter_keys = ['path', 'role_name', 'role_id', 'arn']
        # sort_keys are passed to sorting drop-down
        self.sort_keys = [
            dict(key='role_name', name=_(u'Role name: A to Z')),
            dict(key='-role_name', name=_(u'Role name: Z to A')),
        ]

        return dict(
            filter_fields=False,
            filter_keys=self.filter_keys,
            sort_keys=self.sort_keys,
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
            json_items_endpoint=json_items_endpoint,
            delete_form=self.delete_form,
        )

    @view_config(route_name='roles_delete', request_method='POST')
    def roles_delete(self):
        location = self.request.route_path('roles')
        role_name = self.request.params.get('name')
        role = self.conn.get_role(role_name=role_name)
        if role and self.delete_form.validate():
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Deleting role {0}").format(role.role_name))
                params = {'RoleName': role.role_name, 'IsRecursive': 'true'}
                self.conn.get_response('DeleteRole', params)
                msg = _(u'Successfully deleted role')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to delete role.')  # TODO Pull in form validation error messages here
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=location)


class RolesJsonView(BaseView):
    """Roles returned as JSON"""
    def __init__(self, request):
        super(RolesJsonView, self).__init__(request)
        self.conn = self.get_connection(conn_type="iam")

    @view_config(route_name='roles_json', renderer='json', request_method='GET')
    def roles_json(self):
        # TODO: take filters into account??
        roles = []
        for role in self.get_items():
            policies = []
            try:
                policies = self.conn.list_role_policies(role_name=role.role_name)
                policies = policies.policy_names
            except BotoServerError as exc:
                pass
            """
            user_count = 0
            try:
                role = self.conn.get_role(role_name=role.role_name)
                user_count = len(role.users) if hasattr(role, 'users') else 0
            except BotoServerError as exc:
                pass
            """
            roles.append(dict(
                path=role.path,
                role_name=role.role_name,
                create_date=role.create_date,
                policy_count=len(policies),
            ))
        return dict(results=roles)

    def get_items(self):
        with boto_error_handler(self.request):
            return self.conn.list_roles().roles


class RoleView(BaseView):
    """Views for single Role"""
    TEMPLATE = '../templates/roles/role_view.pt'

    def __init__(self, request):
        super(RoleView, self).__init__(request)
        self.conn = self.get_connection(conn_type="iam")
        self.role = self.get_role()
        self.role_route_id = self.request.matchdict.get('name')
        self.all_users = self.get_all_users_array()
        self.role_form = RoleForm(self.request, role=self.role, formdata=self.request.params or None)
        self.role_update_form = RoleUpdateForm(self.request, role=self.role, formdata=self.request.params or None)
        self.delete_form = DeleteRoleForm(self.request, formdata=self.request.params)
        create_date = parser.parse(self.role.create_date) if self.role else datetime.now()
        self.render_dict = dict(
            role=self.role,
            role_create_date=create_date,
            role_route_id=self.role_route_id,
            all_users=self.all_users,
            role_form=self.role_form,
            role_update_form=self.role_update_form,
            delete_form=self.delete_form,
        )

    def get_role(self):
        role_param = self.request.matchdict.get('name')
        # Return None if the request is to create new role. Prob. No rolename "new" can be created
        if role_param == "new" or role_param is None:
            return None
        role = None
        try:
            role = self.conn.get_role(role_name=role_param)
        except BotoServerError as err:
            pass
        return role

    def get_all_users_array(self):
        role_param = self.request.matchdict.get('name')
        if role_param == "new" or role_param is None:
            return []
        users = []
        # Role's path to be used ?
        if self.conn:
            users = [u.user_name.encode('ascii', 'ignore') for u in self.conn.get_all_users().users]
        return users

    @view_config(route_name='role_view', renderer=TEMPLATE)
    def role_view(self):
        return self.render_dict
 
    @view_config(route_name='role_create', request_method='POST', renderer=TEMPLATE)
    def role_create(self):
        if self.role_form.validate():
            new_role_name = self.request.params.get('role_name') 
            new_path = self.request.params.get('path')
            location = self.request.route_path('role_view', name=new_role_name)
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Creating role {0}").format(new_role_name))
                self.conn.create_role(role_name=new_role_name, path=new_path)
                msg_template = _(u'Successfully created role {role}')
                msg = msg_template.format(role=new_role_name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)

        return self.render_dict

    @view_config(route_name='role_update', request_method='POST', renderer=TEMPLATE)
    def role_update(self):
        if self.role_update_form.validate():
            new_users = self.request.params.getall('input-users-select')
            role_name_param = self.request.params.get('role_name')
            new_role_name = role_name_param if self.role.role_name != role_name_param else None
            new_path = self.request.params.get('path') if self.role.path != self.request.params.get('path') else None
            this_role_name = new_role_name if new_role_name is not None else self.role.role_name
            if new_users is not None:
                self.role_update_users( self.role.role_name, new_users)
            location = self.request.route_path('role_view', name=this_role_name)
            if new_role_name is not None or new_path is not None:
                with boto_error_handler(self.request, location):
                    self.log_request(_(u"Updating role {0}").format(role_name_param))
                    self.role_update_name_and_path(new_role_name, new_path)
            return HTTPFound(location=location)

        return self.render_dict

    @view_config(route_name='role_delete', request_method='POST')
    def role_delete(self):
        if not self.delete_form.validate():
            return JSONResponse(status=400, message="missing CSRF token")
        location = self.request.route_path('roles')
        if self.role is None:
            raise HTTPNotFound()
        with boto_error_handler(self.request, location):
            self.log_request(_(u"Deleting role {0}").format(self.role.role_name))
            params = {'RoleName': self.role.role_name, 'IsRecursive': 'true'}
            self.conn.get_response('DeleteRole', params)
            msg = _(u'Successfully deleted role')
            self.request.session.flash(msg, queue=Notification.SUCCESS)
        return HTTPFound(location=location)

    def role_update_name_and_path(self, new_role_name, new_path):
        this_role_name = new_role_name if new_role_name is not None else self.role.role_name
        self.conn.update_role(self.role.role_name, new_role_name=new_role_name, new_path=new_path)
        msg_template = _(u'Successfully modified role {role}')
        msg = msg_template.format(role=this_role_name)
        self.request.session.flash(msg, queue=Notification.SUCCESS)
        return

    @view_config(route_name='role_policies_json', renderer='json', request_method='GET')
    def role_policies_json(self):
        " ""Return role policies list" ""
        with boto_error_handler(self.request):
            policies = self.conn.list_role_policies(role_name=self.role.role_name)
            return dict(results=policies.policy_names)

    @view_config(route_name='role_policy_json', renderer='json', request_method='GET')
    def role_policy_json(self):
        " ""Return role policies list" ""
        with boto_error_handler(self.request):
            policy_name = self.request.matchdict.get('policy')
            policy = self.conn.get_role_policy(role_name=self.role.role_name, policy_name=policy_name)
            parsed = json.loads(policy.policy_document)
            return dict(results=json.dumps(parsed, indent=2))

    @view_config(route_name='role_update_policy', request_method='POST', renderer='json')
    def role_update_policy(self):
        if not(self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        # calls iam:PutRolePolicy
        policy = self.request.matchdict.get('policy')
        with boto_error_handler(self.request):
            self.log_request(_(u"Updating policy {0} for role {1}").format(policy, self.role.role_name))
            policy_text = self.request.params.get('policy_text')
            result = self.conn.put_role_policy(
                role_name=self.role.role_name, policy_name=policy, policy_document=policy_text)
            return dict(message=_(u"Successfully updated role policy"), results=result)

    @view_config(route_name='role_delete_policy', request_method='POST', renderer='json')
    def role_delete_policy(self):
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        # calls iam:DeleteRolePolicy
        policy = self.request.matchdict.get('policy')
        with boto_error_handler(self.request):
            self.log_request(_(u"Deleting policy {0} for role {1}").format(policy, self.role.role_name))
            result = self.conn.delete_role_policy(role_name=self.role.role_name, policy_name=policy)
            return dict(message=_(u"Successfully deleted role policy"), results=result)

