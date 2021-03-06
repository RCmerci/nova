#    Copyright 2011 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
from oslo_context import context as o_context
from oslo_context import fixture as o_fixture

from nova import context
from nova import exception
from nova import objects
from nova import test
from nova.tests import uuidsentinel as uuids


class ContextTestCase(test.NoDBTestCase):
    # NOTE(danms): Avoid any cells setup by claiming we will
    # do things ourselves.
    USES_DB_SELF = True

    def setUp(self):
        super(ContextTestCase, self).setUp()
        self.useFixture(o_fixture.ClearRequestContext())

    def test_request_context_elevated(self):
        user_ctxt = context.RequestContext('111',
                                           '222',
                                           is_admin=False)
        self.assertFalse(user_ctxt.is_admin)
        admin_ctxt = user_ctxt.elevated()
        self.assertTrue(admin_ctxt.is_admin)
        self.assertIn('admin', admin_ctxt.roles)
        self.assertFalse(user_ctxt.is_admin)
        self.assertNotIn('admin', user_ctxt.roles)

    def test_request_context_sets_is_admin(self):
        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['admin', 'weasel'])
        self.assertTrue(ctxt.is_admin)

    def test_request_context_sets_is_admin_by_role(self):
        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['administrator'])
        self.assertTrue(ctxt.is_admin)

    def test_request_context_sets_is_admin_upcase(self):
        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['Admin', 'weasel'])
        self.assertTrue(ctxt.is_admin)

    def test_request_context_read_deleted(self):
        ctxt = context.RequestContext('111',
                                      '222',
                                      read_deleted='yes')
        self.assertEqual('yes', ctxt.read_deleted)

        ctxt.read_deleted = 'no'
        self.assertEqual('no', ctxt.read_deleted)

    def test_request_context_read_deleted_invalid(self):
        self.assertRaises(ValueError,
                          context.RequestContext,
                          '111',
                          '222',
                          read_deleted=True)

        ctxt = context.RequestContext('111', '222')
        self.assertRaises(ValueError,
                          setattr,
                          ctxt,
                          'read_deleted',
                          True)

    def test_service_catalog_default(self):
        ctxt = context.RequestContext('111', '222')
        self.assertEqual([], ctxt.service_catalog)

        ctxt = context.RequestContext('111', '222',
                service_catalog=[])
        self.assertEqual([], ctxt.service_catalog)

        ctxt = context.RequestContext('111', '222',
                service_catalog=None)
        self.assertEqual([], ctxt.service_catalog)

    def test_service_catalog_cinder_only(self):
        service_catalog = [
                {u'type': u'compute', u'name': u'nova'},
                {u'type': u's3', u'name': u's3'},
                {u'type': u'image', u'name': u'glance'},
                {u'type': u'volume', u'name': u'cinder'},
                {u'type': u'ec2', u'name': u'ec2'},
                {u'type': u'object-store', u'name': u'swift'},
                {u'type': u'identity', u'name': u'keystone'},
                {u'type': None, u'name': u'S_withouttype'},
                {u'type': u'vo', u'name': u'S_partofvolume'}]

        volume_catalog = [{u'type': u'volume', u'name': u'cinder'}]
        ctxt = context.RequestContext('111', '222',
                service_catalog=service_catalog)
        self.assertEqual(volume_catalog, ctxt.service_catalog)

    def test_to_dict_from_dict_no_log(self):
        warns = []

        def stub_warn(msg, *a, **kw):
            if (a and len(a) == 1 and isinstance(a[0], dict) and a[0]):
                a = a[0]
            warns.append(str(msg) % a)

        self.stub_out('nova.context.LOG.warning', stub_warn)

        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['admin', 'weasel'])

        context.RequestContext.from_dict(ctxt.to_dict())

        self.assertEqual(0, len(warns), warns)

    def test_store_when_no_overwrite(self):
        # If no context exists we store one even if overwrite is false
        # (since we are not overwriting anything).
        ctx = context.RequestContext('111',
                                      '222',
                                      overwrite=False)
        self.assertIs(o_context.get_current(), ctx)

    def test_no_overwrite(self):
        # If there is already a context in the cache a new one will
        # not overwrite it if overwrite=False.
        ctx1 = context.RequestContext('111',
                                      '222',
                                      overwrite=True)
        context.RequestContext('333',
                               '444',
                               overwrite=False)
        self.assertIs(o_context.get_current(), ctx1)

    def test_get_context_no_overwrite(self):
        # If there is already a context in the cache creating another context
        # should not overwrite it.
        ctx1 = context.RequestContext('111',
                                      '222',
                                      overwrite=True)
        context.get_context()
        self.assertIs(ctx1, o_context.get_current())

    def test_admin_no_overwrite(self):
        # If there is already a context in the cache creating an admin
        # context will not overwrite it.
        ctx1 = context.RequestContext('111',
                                      '222',
                                      overwrite=True)
        context.get_admin_context()
        self.assertIs(o_context.get_current(), ctx1)

    def test_convert_from_rc_to_dict(self):
        ctx = context.RequestContext(
            111, 222, request_id='req-679033b7-1755-4929-bf85-eb3bfaef7e0b',
            timestamp='2015-03-02T22:31:56.641629')
        values2 = ctx.to_dict()
        expected_values = {'auth_token': None,
                           'domain': None,
                           'instance_lock_checked': False,
                           'is_admin': False,
                           'is_admin_project': True,
                           'project_id': 222,
                           'project_domain': None,
                           'project_name': None,
                           'quota_class': None,
                           'read_deleted': 'no',
                           'read_only': False,
                           'remote_address': None,
                           'request_id':
                               'req-679033b7-1755-4929-bf85-eb3bfaef7e0b',
                           'resource_uuid': None,
                           'roles': [],
                           'service_catalog': [],
                           'show_deleted': False,
                           'tenant': 222,
                           'timestamp': '2015-03-02T22:31:56.641629',
                           'user': 111,
                           'user_domain': None,
                           'user_id': 111,
                           'user_identity': '111 222 - - -',
                           'user_name': None}
        for k, v in expected_values.items():
            self.assertIn(k, values2)
            self.assertEqual(values2[k], v)

    @mock.patch.object(context.policy, 'authorize')
    def test_can(self, mock_authorize):
        mock_authorize.return_value = True
        ctxt = context.RequestContext('111', '222')

        result = ctxt.can(mock.sentinel.rule)

        self.assertTrue(result)
        mock_authorize.assert_called_once_with(
          ctxt, mock.sentinel.rule,
          {'project_id': ctxt.project_id, 'user_id': ctxt.user_id})

    @mock.patch.object(context.policy, 'authorize')
    def test_can_fatal(self, mock_authorize):
        mock_authorize.side_effect = exception.Forbidden
        ctxt = context.RequestContext('111', '222')

        self.assertRaises(exception.Forbidden,
                          ctxt.can, mock.sentinel.rule)

    @mock.patch.object(context.policy, 'authorize')
    def test_can_non_fatal(self, mock_authorize):
        mock_authorize.side_effect = exception.Forbidden
        ctxt = context.RequestContext('111', '222')

        result = ctxt.can(mock.sentinel.rule, mock.sentinel.target,
                          fatal=False)

        self.assertFalse(result)
        mock_authorize.assert_called_once_with(ctxt, mock.sentinel.rule,
                                               mock.sentinel.target)

    @mock.patch('nova.rpc.create_transport')
    @mock.patch('nova.db.create_context_manager')
    def test_target_cell(self, mock_create_ctxt_mgr, mock_rpc):
        mock_create_ctxt_mgr.return_value = mock.sentinel.cdb
        mock_rpc.return_value = mock.sentinel.cmq
        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['admin', 'weasel'])
        # Verify the existing db_connection, if any, is restored
        ctxt.db_connection = mock.sentinel.db_conn
        ctxt.mq_connection = mock.sentinel.mq_conn
        mapping = objects.CellMapping(database_connection='fake://',
                                      transport_url='fake://',
                                      uuid=uuids.cell)
        with context.target_cell(ctxt, mapping) as cctxt:
            self.assertEqual(cctxt.db_connection, mock.sentinel.cdb)
            self.assertEqual(cctxt.mq_connection, mock.sentinel.cmq)
        self.assertEqual(mock.sentinel.db_conn, ctxt.db_connection)
        self.assertEqual(mock.sentinel.mq_conn, ctxt.mq_connection)

    @mock.patch('nova.rpc.create_transport')
    @mock.patch('nova.db.create_context_manager')
    def test_target_cell_unset(self, mock_create_ctxt_mgr, mock_rpc):
        """Tests that passing None as the mapping will temporarily
        untarget any previously set cell context.
        """
        mock_create_ctxt_mgr.return_value = mock.sentinel.cdb
        mock_rpc.return_value = mock.sentinel.cmq
        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['admin', 'weasel'])
        ctxt.db_connection = mock.sentinel.db_conn
        ctxt.mq_connection = mock.sentinel.mq_conn
        with context.target_cell(ctxt, None) as cctxt:
            self.assertIsNone(cctxt.db_connection)
            self.assertIsNone(cctxt.mq_connection)
        self.assertEqual(mock.sentinel.db_conn, ctxt.db_connection)
        self.assertEqual(mock.sentinel.mq_conn, ctxt.mq_connection)

    def test_get_context(self):
        ctxt = context.get_context()
        self.assertIsNone(ctxt.user_id)
        self.assertIsNone(ctxt.project_id)
        self.assertFalse(ctxt.is_admin)

    @mock.patch('nova.rpc.create_transport')
    @mock.patch('nova.db.create_context_manager')
    def test_target_cell_caching(self, mock_create_cm, mock_create_tport):
        mock_create_cm.return_value = mock.sentinel.db_conn_obj
        mock_create_tport.return_value = mock.sentinel.mq_conn_obj
        ctxt = context.get_context()
        mapping = objects.CellMapping(database_connection='fake://db',
                                      transport_url='fake://mq',
                                      uuid=uuids.cell)
        # First call should create new connection objects.
        with context.target_cell(ctxt, mapping) as cctxt:
            self.assertEqual(mock.sentinel.db_conn_obj, cctxt.db_connection)
            self.assertEqual(mock.sentinel.mq_conn_obj, cctxt.mq_connection)
        mock_create_cm.assert_called_once_with('fake://db')
        mock_create_tport.assert_called_once_with('fake://mq')
        # Second call should use cached objects.
        mock_create_cm.reset_mock()
        mock_create_tport.reset_mock()
        with context.target_cell(ctxt, mapping) as cctxt:
            self.assertEqual(mock.sentinel.db_conn_obj, cctxt.db_connection)
            self.assertEqual(mock.sentinel.mq_conn_obj, cctxt.mq_connection)
        mock_create_cm.assert_not_called()
        mock_create_tport.assert_not_called()
