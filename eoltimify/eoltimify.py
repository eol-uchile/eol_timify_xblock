import pkg_resources
import six
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
import requests
import logging
import json
from six import text_type

from xblock.exceptions import JsonHandlerError, NoSuchViewError
from xblock.validation import Validation
from xblockutils.resources import ResourceLoader
from django.conf import settings as DJANGO_SETTINGS
from django.utils import timezone
from django.template import Context, Template
from django.core.cache import cache
from xblock.core import XBlock
from xblock.fields import Integer, Scope, String, Dict, Float, Boolean, List, DateTime, JSONField
from xblock.fragment import Fragment
from xblockutils.studio_editable import StudioEditableXBlockMixin
from opaque_keys.edx.keys import CourseKey, UsageKey
from datetime import datetime
import pytz

log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)
# Make '_' a no-op so we can scrape strings


def _(text): return text


def reify(meth):
    """
    Decorator which caches value so it is only computed once.
    Keyword arguments:
    inst
    """
    def getter(inst):
        """
        Set value to meth name in dict and returns value.
        """
        value = meth(inst)
        inst.__dict__[meth.__name__] = value
        return value
    return property(getter)


class EolTimifyXBlock(StudioEditableXBlockMixin, XBlock):

    display_name = String(
        display_name="Display Name",
        help="Display name for this module",
        default="Eol Timify XBlock",
        scope=Scope.settings,
    )
    duration = Integer(
        display_name="Duracion",
        default=120,
        scope=Scope.settings,
        values={'min': 0},
        help="Duracion del Test"
    )
    autoclose = String(
        display_name="Auto Close",
        help="Display name for this module",
        default="Si",
        values=["Si", "No"],
        scope=Scope.settings,
    )
    idform = String(
        display_name="Formulario",
        help="Cambiar formulario",
        default="",
        scope=Scope.settings
    )
    has_author_view = True
    has_score = True
    editable_fields = ('idform', 'autoclose', 'duration', 'display_name')

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    @reify
    def block_course_id(self):
        """
        Return the course_id of the block.
        """
        return six.text_type(self.course_id)

    @reify
    def block_id(self):
        """
        Return the usage_id of the block.
        """
        return six.text_type(self.scope_ids.usage_id)

    def is_course_staff(self):
        # pylint: disable=no-member
        """
         Check if user is course staff.
        """
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    def is_instructor(self):
        # pylint: disable=no-member
        """
        Check if user role is instructor.
        """
        return self.xmodule_runtime.get_user_role() == 'instructor'

    def show_staff_grading_interface(self):
        """
        Return if current user is staff and not in studio.
        """
        in_studio_preview = self.scope_ids.user_id is None
        return self.is_course_staff() and not in_studio_preview

    def get_link(self, student_id):
        """
        Return student's link
        """
        from lms.djangoapps.courseware.models import StudentModule
        try:
            student_module = StudentModule.objects.get(
                student_id=student_id,
                course_id=self.course_id,
                module_state_key=self.location
            )
        except StudentModule.DoesNotExist:
            student_module = None

        if student_module:
            return json.loads(student_module.state)
        return {}

    def get_or_create_student_module(self, student_id):
        """
        Gets or creates a StudentModule for the given user for this block
        Returns:
            StudentModule: A StudentModule object
        """
        # pylint: disable=no-member
        from lms.djangoapps.courseware.models import StudentModule
        student_module, created = StudentModule.objects.get_or_create(
            course_id=self.course_id,
            module_state_key=self.location,
            student_id=student_id,
            defaults={
                'state': '{}',
                'module_type': self.category,
            }
        )
        if created:
            log.info(
                "Created student module %s [course: %s] [student: %s]",
                student_module.module_state_key,
                student_module.course_id,
                student_module.student.username
            )
        return student_module

    def is_past_due(self):
        """
        Return whether due date has passed.
        """
        from xmodule.util.duedate import get_extended_due_date

        due = get_extended_due_date(self)
        try:
            graceperiod = self.graceperiod
        except AttributeError:
            # graceperiod and due are defined in InheritanceMixin
            # It's used automatically in edX but the unit tests will need to
            # mock it out
            graceperiod = None

        if graceperiod is not None and due:
            close_date = due + graceperiod
        else:
            close_date = due

        if close_date is not None:
            return datetime.now(tz=pytz.utc) > close_date
        return False

    def expired_date(self):
        """
        Return whether due date has passed.
        """
        from xmodule.util.duedate import get_extended_due_date

        due = get_extended_due_date(self)
        try:
            graceperiod = self.graceperiod
        except AttributeError:
            # graceperiod and due are defined in InheritanceMixin
            # It's used automatically in edX but the unit tests will need to
            # mock it out
            graceperiod = None

        if graceperiod is not None and due:
            close_date = due + graceperiod
        else:
            close_date = due

        return close_date

    def author_view(self, context=None):
        context = {'xblock': self, 'location': str(
            self.location).split('@')[-1]}
        template = self.render_template(
            'static/html/author_view.html', context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/eoltimify.css"))
        return frag

    def studio_view(self, context):
        """
        Render a form for editing this XBlock
        """
        fragment = Fragment()

        context = {
            'xblock': self,
            'field_autoclose': self.fields['autoclose'],
            'location': str(self.location).split('@')[-1]
        }
        context['idform'] = self._make_field_info2(
            'idform', self.fields['idform'])

        fragment.content = loader.render_django_template(
            'static/html/studio_view.html', context)
        fragment.add_css(self.resource_string("static/css/eoltimify.css"))
        fragment.add_javascript(self.resource_string(
            "static/js/src/eoltimify_studio.js"))
        fragment.initialize_js('EolTimifyXBlock')
        return fragment

    def student_view(self, context=None):
        context = self.get_context()
        template = self.render_template(
            'static/html/eoltimify.html', context)
        frag = Fragment(template)
        frag.add_css(self.resource_string("static/css/eoltimify.css"))
        frag.add_javascript(self.resource_string(
            "static/js/src/eoltimify.js"))
        frag.initialize_js('EolTimifyXBlock')
        return frag

    def get_context(self):
        aux = self.block_course_id
        course_key = CourseKey.from_string(aux)
        context = {'xblock': self}

        if self.show_staff_grading_interface():
            from dateutil.parser import parse
            context['is_course_staff'] = True
        else:
            context['id_form'] = self.idform
            context['is_course_staff'] = False
            context['timify'] = False
            context["expired"] = False
            context["score"] = "None"
            user_id = self.scope_ids.user_id
            id_form = self.idform

            if self.is_past_due():
                context["expired"] = True
                state = self.get_link(user_id)
                if len(state) > 0:
                    context["score"] = state['score']
                return context

            if id_form != "":
                connectsid, apiKey = self.get_api_token()
                if connectsid is False:
                    return context
                student_module = self.get_or_create_student_module(user_id)
                state = json.loads(student_module.state)
                if len(state) == 0:
                    context = self.create_link(
                        context, connectsid, apiKey, student_module, state)

                elif state["id_form"] == id_form:
                    from dateutil.parser import parse
                    context['done'] = self.get_done(
                        state['id_link'], connectsid, apiKey)
                    context['timify'] = True
                    context['link'] = "https://timify.me/link/" + state['link']
                    context['name_link'] = state['name_link']
                    context['id_form'] = id_form
                    context['score'] = state['score']

                    expired_date = self.expired_date()
                    if state['expired'] is not None and expired_date is not None:
                        context['late'] = parse(
                            state['expired']) > expired_date
                    else:
                        context['late'] = "Sin Registros"
                else:
                    context = self.create_link(
                        context, connectsid, apiKey, student_module, state)

        return context

    def create_link(self, context, connectsid, apiKey, student_module, state):
        from django.contrib.auth.models import User
        user_id = self.scope_ids.user_id
        id_form = self.idform
        times = self.duration
        fClose = True if self.autoclose == "Si" else False
        pageId = int(id_form)
        student = User.objects.filter(
            id=user_id).order_by('username').values(
            'id', 'username', 'email')
        links = [{"text": student[0]['username']}]

        parameters = {
            "labels": links,
            "expiresIn": times,
            "forceClose": fClose,
            "pageId": pageId}  # links=[{"text":"test1"},{"text":"test3"},{"text":"test4"}]

        result = requests.post(
            "https://timify.me/api/v1/~/Link/bulk",
            data=json.dumps(parameters),
            cookies={
                'connect.sid': connectsid},
            headers={
                'content-type': 'application/json',
                "x-api-key": apiKey})

        if result.status_code == 200:
            datajson = json.loads(result.text)
            state['id_form'] = id_form
            state['link'] = datajson['links'][0]['hash']
            state['name_link'] = datajson['links'][0]['label']
            state['id_link'] = str(datajson['links'][0]['id'])
            state['score'] = 'Sin Registros'
            state['expired'] = None
            context['timify'] = True
            context['done'] = False
            student_module.state = json.dumps(state)
            student_module.save()
            context['link'] = "https://timify.me/link/" + \
                state['link']
            context['name_link'] = state['name_link']
            context['id_form'] = id_form
            context['score'] = state['score']
            context['late'] = "Sin Registros"

        return context

    def get_done(self, id_link, connectsid, apiKey):
        id_form = self.idform
        result = requests.get(
            "https://timify.me/api/v1/~/Page/@id/" +
            id_form +
            "/with/Link",
            cookies={
                'connect.sid': connectsid},
            headers={
                'content-type': 'application/json',
                "x-api-key": apiKey})

        if result.status_code == 200:
            datajson = json.loads(result.text)
            for link in datajson["page"]["links"]:
                if str(link['id']) == id_link:
                    return link['finishedAt'] is not None
        return False

    def get_api_token(self):
        data = cache.get("eol_timify-" + self.block_course_id + "-apikey")
        if data is None:
            connectsid = ""
            if DJANGO_SETTINGS.TIMIFY_USER != "" and DJANGO_SETTINGS.TIMIFY_PASSWORD != "":
                parameters = {
                    "username": DJANGO_SETTINGS.TIMIFY_USER,
                    "password": DJANGO_SETTINGS.TIMIFY_PASSWORD}
                result = requests.post(
                    "https://timify.me/api/v1/auth/ep",
                    data=json.dumps(parameters),
                    headers={
                        'content-type': 'application/json'})
                if result.status_code == 200:
                    headers = result.headers["Set-Cookie"].split(";")
                    for header in headers:
                        if "connect.sid" in header:
                            aux_id = header.split("=")
                            connectsid = aux_id[2]

                    result_api = requests.get(
                        "https://timify.me/api/v1/~/Session",
                        cookies={
                            'connect.sid': connectsid},
                        headers={
                            'content-type': 'application/json'})
                    if result_api.status_code == 200:
                        data = json.loads(result_api.text)
                        cache_data = [connectsid, data["session"]["api_token"]]
                        cache.set("eol_timify-" + self.block_course_id + "-apikey", cache_data, DJANGO_SETTINGS.EOL_TIMIFY_TIME_CACHE)
                        return cache_data[0], cache_data[1]
        else:
            return data[0], data[1]
        return False, False

    @XBlock.json_handler
    def show_score(self, data, suffix=''):

        pageId = self.idform
        user_id = self.scope_ids.user_id
        connectsid, apiKey = self.get_api_token()
        if connectsid is False:
            return {'result': 'error'}
        result = requests.get(
            "https://timify.me/api/v1/~/Page/@id/" +
            pageId +
            "/with/Link",
            cookies={
                'connect.sid': connectsid},
            headers={
                'content-type': 'application/json',
                "x-api-key": apiKey})

        if result.status_code == 200:
            from django.contrib.auth.models import User
            from dateutil.parser import parse
            aux = self.block_course_id
            course_key = CourseKey.from_string(aux)
            enrolled_students = User.objects.filter(
                courseenrollment__course_id=course_key,
                courseenrollment__is_active=1
            ).order_by('username').values('id', 'username', 'email')
            datajson = json.loads(result.text)
            aux_links = datajson["page"]["links"]
            if len(aux_links) > 0:
                links = {}
                for link in aux_links:
                    ids = str(link['id'])
                    links[ids] = [str(link['score']) if link['score']
                                  is not None else "Sin Registros", link["finishedAt"]]
                list_student = []
                for student in enrolled_students:
                    student_module = self.get_or_create_student_module(
                        student['id'])
                    state = json.loads(student_module.state)

                    if len(state) > 0 and state['id_link'] in links:
                        id_link = state['id_link']
                        expired_date = self.expired_date()
                        if links[id_link][1] is not None and expired_date is not None:
                            aux_date = "Si" if parse(
                                links[id_link][1]) > expired_date else "No"
                        else:
                            aux_date = "Sin Registros"
                        list_student.append([student['id'],
                                             student['username'],
                                             student['email'],
                                             state['name_link'],
                                             links[id_link][0],
                                             aux_date])
                        state['score'] = links[id_link][0]
                        state['expired'] = links[id_link][1]
                        student_module.state = json.dumps(state)
                        student_module.save()
                    elif len(state) > 0:
                        list_student.append([student['id'],
                                             student['username'],
                                             student['email'],
                                             state['name_link'],
                                             "Sin Registros",
                                             "Sin Registros"])
                    else:
                        list_student.append([student['id'],
                                             student['username'],
                                             student['email'],
                                             "Sin Registros",
                                             "Sin Registros",
                                             "Sin Registros"])
                return {
                    'result': 'success',
                    'list_student': list_student}
            else:
                return {'result': 'error2'}

        return {'result': 'error'}

    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        Called when submitting the form in Studio.
        """
        self.display_name = data.get(
            'display_name') or self.display_name.default
        self.duration = int(data.get('duration')) or self.duration.default
        self.autoclose = data.get('autoclose') or self.autoclose.default
        self.idform = data.get('idform') or ""
        return {'result': 'success'}

    def render_template(self, template_path, context):
        template_str = self.resource_string(template_path)
        template = Template(template_str)
        return template.render(Context(context))

        # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("EolTimifyXBlock",
             """<eoltimify/>
             """),
            ("Multiple EolTimifyXBlock",
             """<vertical_demo>
                <eoltimify/>
                <eoltimify/>
                <eoltimify/>
                </vertical_demo>
             """),
        ]

    def get_idform(self):
        connectsid, apiKey = self.get_api_token()
        list_form = [connectsid, apiKey]
        if connectsid is not False:

            result = requests.get(
                "https://timify.me/api/v1/~/Page/all",
                cookies={
                    'connect.sid': connectsid},
                headers={
                    'content-type': 'application/json',
                    "x-api-key": apiKey})
            data = json.loads(result.text)
            list_form = [{"display_name": x['label'],
                          "value": str(x['id'])} for x in data['pages']]
        return list_form

    def _make_field_info2(self, field_name, field):  # pylint: disable=too-many-statements
        """
        Create the information that the template needs to render a form field for this field.
        """
        if self.service_declaration("i18n"):
            ugettext = self.ugettext
        else:

            def ugettext(text):
                """ Dummy ugettext method that doesn't do anything """
                return text

        info = {
            'name': field_name,
            # pylint: disable=translation-of-non-string
            'display_name': ugettext(field.display_name) if field.display_name else "",
            'is_set': field.is_set_on(self),
            'default': field.default,
            'value': field.read_from(self),
            'type': 'string',
            'has_values': False,
            # pylint: disable=translation-of-non-string
            'help': ugettext(field.help) if field.help else "",
            'allow_reset': field.runtime_options.get('resettable_editor', True),
            'list_values': None,  # Only available for List fields
            # True if list_values_provider exists, even if it returned no
            # available options
            'has_list_values': False,
        }

        values = self.get_idform()
        info['values'] = values
        if len(values) > 0 and not isinstance(field, Boolean):
            # This field has only a limited number of pre-defined options.
            # Protip: when defining the field, values= can be a callable.
            if isinstance(
                    values[0],
                    dict) and "display_name" in values[0] and "value" in values[0]:
                # e.g. [ {"display_name": "Always", "value": "always"}, ... ]
                for value in values:
                    assert "display_name" in value and "value" in value
                info['values'] = values
            else:
                # e.g. [1, 2, 3] - we need to convert it to the
                # [{"display_name": x, "value": x}] format
                info['values'] = [{"display_name": text_type(
                    val), "value": val} for val in values]
            info['has_values'] = 'values' in info

        return info
