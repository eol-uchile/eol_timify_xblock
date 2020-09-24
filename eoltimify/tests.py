"""
Module To Test EolTimify XBlock
"""
from django.test import TestCase, Client
from collections import namedtuple
from mock import MagicMock, Mock, patch
from django.contrib.auth.models import User
from util.testing import UrlResetMixin
from opaque_keys.edx.locations import Location
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from student.roles import CourseStaffRole
from django.test.client import RequestFactory
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from lms.djangoapps.courseware.tests.factories import StudentModuleFactory
from xblock.field_data import DictFieldData
from opaque_keys.edx.locator import CourseLocator
from .eoltimify import EolTimifyXBlock
from django.test.utils import override_settings

import json
import unittest
import logging
import mock

log = logging.getLogger(__name__)


class TestRequest(object):
    # pylint: disable=too-few-public-methods
    """
    Module helper for @json_handler
    """
    method = None
    body = None
    success = None


class EolTimifyXBlockTestCase(UrlResetMixin, ModuleStoreTestCase):
    # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """
    A complete suite of unit tests for the EolTimify XBlock
    """

    def make_an_xblock(cls, **kw):
        """
        Helper method that creates a EolTimify XBlock
        """

        course = cls.course
        runtime = Mock(
            course_id=course.id,
            user_is_staff=False,
            service=Mock(
                return_value=Mock(_catalog={}),
            ),
        )
        scope_ids = Mock()
        field_data = DictFieldData(kw)
        xblock = EolTimifyXBlock(runtime, field_data, scope_ids)
        xblock.xmodule_runtime = runtime
        xblock.location = course.location
        xblock.course_id = course.id
        xblock.category = 'eoltimify'
        return xblock

    def setUp(self):
        super(EolTimifyXBlockTestCase, self).setUp()
        """
        Creates an xblock
        """
        self.course = CourseFactory.create(org='foo', course='baz', run='bar')

        self.xblock = self.make_an_xblock()

        with patch('student.models.cc.User.save'):
            # Create the student
            self.student = UserFactory(
                username='student',
                password='test',
                email='student@edx.org')
            # Enroll the student in the course
            CourseEnrollmentFactory(
                user=self.student, course_id=self.course.id)

            # Create staff user
            self.staff_user = UserFactory(
                username='staff_user',
                password='test',
                email='staff@edx.org')
            CourseEnrollmentFactory(
                user=self.staff_user,
                course_id=self.course.id)
            CourseStaffRole(self.course.id).add_users(self.staff_user)

    def test_validate_field_data(self):
        self.assertEqual(self.xblock.display_name, 'Eol Quilgo XBlock')
        self.assertEqual(self.xblock.duration, 120)
        self.assertEqual(self.xblock.autoclose, "Si")
        self.assertEqual(self.xblock.idform, "")

    def test_edit_block_studio(self):
        """
            Check if it's working submit studio edits
        """
        request = TestRequest()
        request.method = 'POST'
        self.xblock.xmodule_runtime.user_is_staff = True
        data = json.dumps({'display_name': 'testname',
                           "duration": '200',
                           "autoclose": 'No',
                           "idform": '11223344'}).encode()
        request.body = data
        response = self.xblock.studio_submit(request)
        self.assertEqual(self.xblock.display_name, 'testname')
        self.assertEqual(self.xblock.duration, 200)
        self.assertEqual(self.xblock.autoclose, "No")
        self.assertEqual(self.xblock.idform, "11223344")

    def test_staff_user_view(self):
        """
            Verify the staff user view
        """
        self.xblock.xmodule_runtime.user_is_staff = True

        response = self.xblock.student_view()
        self.assertTrue('name="show"' in response.content)

    @override_settings(TIMIFY_USER="")
    @override_settings(TIMIFY_PASSWORD="")
    def test_student_user_view_no_id_form(self):
        """
            Verify student view if the xblock dont have id form
        """
        self.xblock.xmodule_runtime.user_is_staff = False

        response = self.xblock.student_view()
        self.assertTrue('Sin Datos' in response.content)

    @override_settings(TIMIFY_USER="")
    @override_settings(TIMIFY_PASSWORD="")
    def test_student_user_view_no_setting(self):
        """
            Verify student view if the xblock dont have user/password in settings
        """
        from lms.djangoapps.courseware.models import StudentModule
        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{}')
        module.save()

        response = self.xblock.student_view()
        self.assertTrue('Sin Datos' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view(self, get, post):
        """
            Test student view normal process
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request", ["status_code", "text"])(
            200, json.dumps({"session": {"api_token": "test_token"}}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{}')
        module.save()

        response = self.xblock.student_view()
        state = StudentModule.objects.get(pk=module.id)
        self.assertEqual(
            json.loads(state.state),
            json.loads('{"name_link": "test", "id_link": "1", "score": "Sin Registros", "link": "testhash", "id_form": "11223344", "expired": null}'))
        self.assertTrue(
            'href=https://quilgo.com/link/testhash ' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_post_1_400(self, get, post):
        """
            Test student view when get connect.ids fail
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request", ["status_code", "text"])(
            200, json.dumps({"session": {"api_token": "test_token"}}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers", "content"])(
                400, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}, 'error'), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{}')
        module.save()

        response = self.xblock.student_view()

        self.assertTrue('Sin Datos' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_post_2_400(self, get, post):
        """
            Test student view when get id form fail
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request", ["status_code", "text"])(
            200, json.dumps({"session": {"api_token": "test_token"}}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text", "content"])(
                                400, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}), 'error')]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{}')
        module.save()

        response = self.xblock.student_view()

        self.assertTrue('Sin Datos' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_get_1_400(self, get, post):
        """
            Test student view when get api-key fail
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request", ["status_code", "text", "content"])(
            400, json.dumps({"session": {"api_token": "test_token"}}), 'error')]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{}')
        module.save()

        response = self.xblock.student_view()

        self.assertTrue('Sin Datos' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_with_module_state_finished(self, get, post):
        """
            Test student view when link is already finished
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "hash": "testhash",
                                                                    "label": "test",
                                                                    "finishedAt": "2020-05-11T15:37:55.000Z"}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "2", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": "2020-05-11T15:37:55.000Z"}')
        module.save()

        response = self.xblock.student_view()

        self.assertTrue('<label>Puntaje: 2</label>' in response.content)
        self.assertTrue('id="finished"' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_with_module_state(self, get, post):
        """
            Test student view when student already have student_module
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "hash": "testhash",
                                                                    "label": "test",
                                                                    "finishedAt": None}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": null}')
        module.save()

        response = self.xblock.student_view()
        self.assertTrue(
            'href=https://quilgo.com/link/testhash ' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_with_different_id_form(self, get, post):
        """
            Test student view when student already have student_module and if form is different
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "hash": "testhash",
                                                                    "label": "test",
                                                                    "finishedAt": None}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "55667788"
        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": null}')
        module.save()

        response = self.xblock.student_view()
        self.assertTrue(
            'href=https://quilgo.com/link/testhash ' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_with_false_past_due_form_no_completed(
            self,
            get,
            post):
        """
            Test student view when section is finished and link is expired
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request", ["status_code", "text"])(
            200, json.dumps({"session": {"api_token": "test_token"}}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id
        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{}')
        module.save()
        with mock.patch('eoltimify.eoltimify.EolTimifyXBlock.is_past_due', return_value=True):
            response = self.xblock.student_view()

        self.assertTrue('id="expired"' in response.content)
        self.assertTrue('Formulario no realizado' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_student_user_view_with_false_past_due_form_completed(
            self, get, post):
        """
            Test student view when section is finished
        """
        from lms.djangoapps.courseware.models import StudentModule
        get.side_effect = [namedtuple("Request", ["status_code", "text"])(
            200, json.dumps({"session": {"api_token": "test_token"}}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.xmodule_runtime.user_is_staff = False
        self.xblock.scope_ids.user_id = self.student.id

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "2", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": "2020-05-11T15:37:55.000Z"}')
        module.save()
        with mock.patch('eoltimify.eoltimify.EolTimifyXBlock.is_past_due', return_value=True):
            response = self.xblock.student_view()
        self.assertTrue('id="expired"' in response.content)
        self.assertTrue('<label>Puntaje: 2</label>' in response.content)

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_show_score(self, get, post):
        """
            Test staff view normal process
        """
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "score": "1",
                                                                    "finishedAt": "2020-05-11T15:37:55.000Z"},
                                                                    {"id": 2,
                                                                    "score": None,
                                                                    "finishedAt": None}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data

        response = self.xblock.show_score(request)
        data = json.loads(response._app_iter[0].decode())
        list_student = [[self.staff_user.id,
                         'staff_user',
                         'staff@edx.org',
                         'Sin Registros',
                         'Sin Registros',
                         'Sin Registros'],
                        [self.student.id,
                         'student',
                         'student@edx.org',
                         'Sin Registros',
                         'Sin Registros',
                         'Sin Registros']]
        self.assertEqual(data["list_student"], list_student)
        self.assertEqual(data["result"], "success")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_post_1_400(self, get, post):
        """
            Test staff view when get connect.ids fail
        """
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request", ["status_code", "text"])(200, json.dumps({"session": {"api_token": "test_token"}})), namedtuple(
            "Request", ["status_code", "text"])(200, json.dumps({"page": {"links": [{"id": 1, "score": "1"}, {"id": 2, "score": None}]}}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers", "content"])(
                400, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}, 'error'), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data
        response = self.xblock.show_score(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data["result"], "error")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_post_2_400(self, get, post):
        """
            Test staff view when get links from form fail
        """
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request", ["status_code", "text"])(200, json.dumps({"session": {"api_token": "test_token"}})), namedtuple(
            "Request", ["status_code", "text", "content"])(400, json.dumps({"page": {"links": [{"id": 1, "score": "1"}, {"id": 2, "score": None}]}}), 'error')]
        post.side_effect = [namedtuple("Request", ["status_code", "headers"])(
            200, {'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'})]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data
        response = self.xblock.show_score(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data["result"], "error")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_get_1_400(self, get, post):
        """
            Test staff view when get api-key fail
        """
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request", ["status_code", "text", "content"])(400, json.dumps({"session": {"api_token": "test_token"}}), 'error'), namedtuple(
            "Request", ["status_code", "text"])(200, json.dumps({"page": {"links": [{"id": 1, "score": "1"}, {"id": 2, "score": None}]}}))]
        post.side_effect = [namedtuple("Request", ["status_code", "headers"])(
            200, {'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'})]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data
        response = self.xblock.show_score(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data["result"], "error")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_no_links(self, get, post):
        """
            Test staff view when form dont have links
        """
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "text"])(
                200, json.dumps(
                    {
                        "session": {
                            "api_token": "test_token"}})), namedtuple(
                                "Request", [
                                    "status_code", "text"])(
                                        200, json.dumps(
                                            {"links": []}))]
        post.side_effect = [namedtuple("Request", ["status_code", "headers"])(
            200, {'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'})]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data
        response = self.xblock.show_score(request)
        data = json.loads(response._app_iter[0].decode())
        self.assertEqual(data["result"], "error2")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_state_link(self, get, post):
        """
            Test staff view when student have student_module
        """
        from lms.djangoapps.courseware.models import StudentModule
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "score": "1",
                                                                    "finishedAt": "2020-05-11T15:37:55.000Z"},
                                                                    {"id": 2,
                                                                    "score": None,
                                                                    "finishedAt": None}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": "2020-05-11T15:37:55.000Z"}')
        module.save()

        module2 = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.staff_user.id,
            course_id=self.course.id,
            state='{"id_link": "2", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": null}')
        module2.save()

        response = self.xblock.show_score(request)
        data = json.loads(response._app_iter[0].decode())
        list_student = [[self.staff_user.id,
                         'staff_user',
                         'staff@edx.org',
                         'test',
                         'Sin Registros',
                         'Sin Registros'],
                        [self.student.id,
                         'student',
                         'student@edx.org',
                         'test',
                         '1',
                         'Sin Registros']]
        self.assertEqual(data["list_student"], list_student)
        self.assertEqual(data["result"], "success")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_state_no_link(self, get, post):
        """
            Test staff view when link from student molude no exists in link from form
        """
        from lms.djangoapps.courseware.models import StudentModule
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "score": "1",
                                                                    "finishedAt": "2020-05-11T15:37:55.000Z"},
                                                                    {"id": 2,
                                                                    "score": None,
                                                                    "finishedAt": None}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": null}')
        module.save()

        module2 = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.staff_user.id,
            course_id=self.course.id,
            state='{"id_link": "5", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344"}')
        module2.save()

        response = self.xblock.show_score(request)
        data = json.loads(response._app_iter[0].decode())
        list_student = [[self.staff_user.id,
                         'staff_user',
                         'staff@edx.org',
                         'test',
                         'Sin Registros',
                         'Sin Registros'],
                        [self.student.id,
                         'student',
                         'student@edx.org',
                         'test',
                         '1',
                         'Sin Registros']]
        self.assertEqual(data["list_student"], list_student)
        self.assertEqual(data["result"], "success")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_with_datetime(self, get, post):
        """
            Test staff view when section have finished date time
        """
        from lms.djangoapps.courseware.models import StudentModule
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "score": "1",
                                                                    "finishedAt": "2020-05-11T15:37:55.000Z"},
                                                                    {"id": 2,
                                                                    "score": None,
                                                                    "finishedAt": None}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": "2020-05-11T15:37:55.000Z"}')
        module.save()

        module2 = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.staff_user.id,
            course_id=self.course.id,
            state='{"id_link": "2", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": null}')
        module2.save()
        from dateutil.parser import parse
        with mock.patch('eoltimify.eoltimify.EolTimifyXBlock.expired_date', return_value=parse("2020-05-11T15:38:55.000Z")):
            response = self.xblock.show_score(request)

        data = json.loads(response._app_iter[0].decode())
        list_student = [[self.staff_user.id,
                         'staff_user',
                         'staff@edx.org',
                         'test',
                         'Sin Registros',
                         'Sin Registros'],
                        [self.student.id,
                         'student',
                         'student@edx.org',
                         'test',
                         '1',
                         'No']]
        self.assertEqual(data["list_student"], list_student)
        self.assertEqual(data["result"], "success")

    @override_settings(TIMIFY_USER="test")
    @override_settings(TIMIFY_PASSWORD="test")
    @patch('requests.post')
    @patch('requests.get')
    def test_staff_user_view_with_datetime_late(self, get, post):
        """
            Test staff view when finished datetime section is already finished
        """
        from lms.djangoapps.courseware.models import StudentModule
        request = TestRequest()
        request.method = 'POST'

        get.side_effect = [namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"session": {"api_token": "test_token"}})),
                           namedtuple("Request",
                                      ["status_code",
                                       "text"])(200,
                                                json.dumps({"links": [{"id": 1,
                                                                    "score": "1",
                                                                    "finishedAt": "2020-05-11T15:37:55.000Z"},
                                                                    {"id": 2,
                                                                    "score": None,
                                                                    "finishedAt": None}]}))]
        post.side_effect = [
            namedtuple(
                "Request", [
                    "status_code", "headers"])(
                200, {
                    'Set-Cookie': 'Domain=quilgo.com; Path=/, connect.sid=test;'}), namedtuple(
                        "Request", [
                            "status_code", "text"])(
                                200, json.dumps(
                                    {
                                        "links": [
                                            {
                                                "id": 1, "hash": "testhash", "label": "test"}]}))]

        self.xblock.idform = "11223344"
        self.xblock.xmodule_runtime.user_is_staff = True
        self.xblock.scope_ids.user_id = self.staff_user.id
        data = b'{}'
        request.body = data

        module = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.student.id,
            course_id=self.course.id,
            state='{"id_link": "1", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": "2020-05-11T15:37:55.000Z"}')
        module.save()

        module2 = StudentModule(
            module_state_key=self.xblock.location,
            student_id=self.staff_user.id,
            course_id=self.course.id,
            state='{"id_link": "2", "score": "Sin Registros", "link": "testhash", "name_link": "test", "id_form": "11223344", "expired": null}')
        module2.save()
        from dateutil.parser import parse
        with mock.patch('eoltimify.eoltimify.EolTimifyXBlock.expired_date', return_value=parse("2020-05-11T15:36:55.000Z")):
            response = self.xblock.show_score(request)

        data = json.loads(response._app_iter[0].decode())
        list_student = [[self.staff_user.id,
                         'staff_user',
                         'staff@edx.org',
                         'test',
                         'Sin Registros',
                         'Sin Registros'],
                        [self.student.id,
                         'student',
                         'student@edx.org',
                         'test',
                         '1',
                         'Si']]
        self.assertEqual(data["list_student"], list_student)
        self.assertEqual(data["result"], "success")
