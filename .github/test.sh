#!/bin/dash

pip install -e /openedx/requirements/eol_timify_xblock
cd /openedx/requirements/eol_timify_xblock/eoltimify
cp /openedx/edx-platform/setup.cfg .
mkdir test_root
cd test_root/
ln -s /openedx/staticfiles .

cd /openedx/requirements/eol_timify_xblock/eoltimify
DJANGO_SETTINGS_MODULE=lms.envs.test EDXAPP_TEST_MONGO_HOST=mongodb pytest tests.py