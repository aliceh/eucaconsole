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
Forms for S3 buckets and objects

"""
import wtforms

from boto.s3.key import Key
from boto.s3.bucket import Bucket
from wtforms import validators

from . import BaseSecureForm, BLANK_CHOICE
from ..i18n import _
from ..forms import TextEscapedField


class BucketDetailsForm(BaseSecureForm):
    """S3 BucketDetails form"""
    pass


class BucketItemDetailsForm(BaseSecureForm):
    """S3 Bucket item (folder/object) form"""
    friendly_name_error_msg = _(
        'Name is required and may not contain "/" characters or may not modify the file extension')
    friendly_name = TextEscapedField(
        label=_(u'Name'),
        validators=[validators.DataRequired(message=friendly_name_error_msg)]
    )

    def __init__(self, request, bucket_object=None, unprefixed_name='', **kwargs):
        super(BucketItemDetailsForm, self).__init__(request, **kwargs)
        self.bucket_object = bucket_object
        self.unprefixed_name = unprefixed_name
        self.friendly_name_pattern = self.get_friendly_name_pattern()
        if bucket_object:
            self.friendly_name.data = unprefixed_name
            self.friendly_name.error_msg = self.friendly_name_error_msg

    def get_friendly_name_pattern(self):
        """Get the friendly name patter to prevent file extension modification"""
        no_slashes_pattern = '[^\/]+'
        if '.' in self.unprefixed_name:
            suffix = self.unprefixed_name.split('.')[-1]
            return '^{0}\.{1}$'.format(no_slashes_pattern, suffix)
        return '^{0}$'.format(no_slashes_pattern)


class BucketUpdateVersioningForm(BaseSecureForm):
    """Update versioning info form"""
    pass


class BucketDeleteForm(BaseSecureForm):
    """Delete form"""
    pass


class BucketUploadForm(BaseSecureForm):
    """Upload form"""
    pass


class SharingPanelForm(BaseSecureForm):
    """S3 Sharing Panel form for buckets/objects"""
    SHARE_TYPE_CHOICES = (('public', _(u'Public')), ('private', _(u'Private')))
    share_type = wtforms.RadioField(choices=SHARE_TYPE_CHOICES)
    share_account_error_msg = _(
        u'Account ID may contain alpha-numeric characters and is a 12-digit account ID or the 64-digit canonical ID.')
    share_account_helptext = _(
        u"Enter an account ID or a user's email address. If you enter an email address, sharing will be extended to all users in their account."
    )
    share_account = TextEscapedField(label=_(u'Account'))
    share_permissions = wtforms.SelectField(label=_(u'Permissions'))
    canned_acl = wtforms.SelectField()

    def __init__(self, request, bucket_object=None, sharing_acl=None, **kwargs):
        super(SharingPanelForm, self).__init__(request, **kwargs)
        self.bucket_object = bucket_object
        self.is_object = isinstance(bucket_object, Key)
        self.sharing_acl = sharing_acl
        # Set error messages
        self.share_account.error_msg = self.share_account_error_msg
        # Set choices
        self.share_permissions.choices = self.get_permission_choices()
        self.canned_acl.choices = self.get_canned_acl_choices()
        # Set help text
        self.share_account.help_text = self.share_account_helptext

        if bucket_object is not None:
            self.share_type.data = self.get_share_type()

        if bucket_object is None:
            self.share_type.data = 'private'

    def get_share_type(self):
        if 'AllUsers = READ' in str(self.sharing_acl):
            return 'public'
        return 'private'

    def get_canned_acl_choices(self):
        choices = [
            ('private', _('Private')),
            ('public-read', _('Public read')),
            ('public-read-write', _('Public read-write')),
            ('authenticated-read', _('Authenticated read')),
        ]
        if self.bucket_object is not None and not isinstance(self.bucket_object, Bucket):
            choices.extend([
                ('bucket-owner-read', _('Bucket owner read')),
                ('bucket-owner-full-control', _('Bucket owner full control')),
            ])
        return choices

    def get_permission_choices(self):
        choices = (
            ('FULL_CONTROL', _('Full Control')),
            ('READ', _('Read-only') if self.is_object else _('List objects')),
            ('WRITE', _('Create/delete objects')) if not self.is_object else None,  # Hide for object details
            ('READ_ACP', _('Read sharing permissions')),
            ('WRITE_ACP', _('Write sharing permissions')),
        )
        return [choice for choice in choices if choice is not None]


class MetadataForm(BaseSecureForm):
    """Form for S3 object metadata"""
    metadata_key = wtforms.SelectField(label=_(u'Key'))
    metadata_value = TextEscapedField(label=_(u'Value'))
    metadata_content_type = wtforms.SelectField(label=_(u'Value'))

    def __init__(self, request, **kwargs):
        super(MetadataForm, self).__init__(request, **kwargs)
        self.request = request
        # Set choices
        self.metadata_key.choices = self.get_metadata_key_choices()
        self.metadata_content_type.choices = self.get_content_type_choices()

    def get_metadata_key_choices(self):
        choices = [
            BLANK_CHOICE,
            ('Cache-Control', _('Cache-Control')),
            ('Content-Disposition', _('Content-Disposition')),
            ('Content-Type', _('Content-Type')),
            ('Content-Language', _('Content-Language')),
            ('Content-Encoding', _('Content-Encoding')),
        ]
        if self.request.session.get('cloud_type') == 'aws':
            choices.extend([
                ('Website-Redirect-Location', _('Website-Redirect-Location')),
                ('x-amz-meta', _('x-amz-meta')),
            ])
        return choices

    @staticmethod
    def get_content_type_choices():
        """Note that this is by no means a comprehensive list.
           We're simply mirroring the choices in the AWS Mgmt Console (as of mid-2014)"""
        content_types = [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/bmp',
            'image/tiff',
            'text/plain',
            'text/rtf',
            'application/msword',
            'application/zip',
            'audio/mpeg',
            'application/pdf',
            'application/x-gzip',
            'application/x-compressed',
        ]
        choices = [BLANK_CHOICE]
        choices.extend([(ct, ct) for ct in content_types])
        return choices


class CreateBucketForm(BaseSecureForm):
    """S3 Create Bucket form"""
    bucket_name_error_msg = _(
        'Name is required and may contain lowercase letters, numbers, hyphens, and/or dots')
    bucket_name = TextEscapedField(
        label=_(u'Name'),
        validators=[
            validators.DataRequired(message=bucket_name_error_msg),
            validators.Length(max=63, message=_(u'Bucket name must not exceed 63 characters')),
        ]
    )
    enable_versioning = wtforms.BooleanField(
        label=_(u'Enable versioning')
    )

    def __init__(self, request, **kwargs):
        super(CreateBucketForm, self).__init__(request, **kwargs)
        self.bucket_name.error_msg = self.bucket_name_error_msg
        self.enable_versioning.help_text = _(
            u'With versioning enabled, objects are prevented from being deleted or overwritten by mistake.')


class CreateFolderForm(BaseSecureForm):
    """S3 Create Folder form"""
    folder_name_error_msg = _('Name is required and may not contain slashes')
    folder_name = TextEscapedField(
        label=_(u'Name'),
        validators=[
            validators.DataRequired(message=folder_name_error_msg),
        ]
    )

    def __init__(self, request, **kwargs):
        super(CreateFolderForm, self).__init__(request, **kwargs)
        self.folder_name.error_msg = self.folder_name_error_msg
