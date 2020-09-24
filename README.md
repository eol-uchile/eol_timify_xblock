# Eol Quilgo XBlock

XBlock and API to integrate quilgo(before timify) with the Open edX LMS. Editable within Open edx Studio.

# Install

    docker-compose exec cms pip install -e /openedx/requirements/eol_timify_xblock
    docker-compose exec lms pip install -e /openedx/requirements/eol_timify_xblock
    docker-compose exec cms_worker pip install -e /openedx/requirements/eol_timify_xblock
    docker-compose exec lms_worker pip install -e /openedx/requirements/eol_timify_xblock

# Configuration

To enable Timify API Edit *production.py* in *lms and cms settings* and add timify account (email and password).
    
    TIMIFY_USER = ""
    TIMIFY_PASSWORD = ""
    EOL_TIMIFY_TIME_CACHE = 300
    

## TESTS
**Prepare tests:**

    > cd .github/
    > docker-compose run lms /openedx/requirements/eol_timify_xblock/.github/test.sh

# Notes

## In Studio
  - If the timify account is not configured, the forms will not be loaded
  - The forms are obtained from all the forms that are associated in the timify account
  - It is recommended to delete the Demo form, since you cannot create tests on this form
  - The forms are automatically updated when opening 'Edit'.

## In Student View
  - If the score is not updated by the instructor it will appear as "Sin Registros"
  ### Instructor
  - A button will be displayed, which updates/shows the score obtained by each student, if the student has not realized the test, has not entered the xblock or if the test has been performed and then removed from timify, the score and/or name of the test will be as "Sin Registros"
  - On the button, when an error occurs in the API call, it will show an error message
  - On the button, when the API call returns an empty list, it will show an error message
  ### Student
  - If the timify account is not configured it will show "Sin Datos"
  
  **If Expired Delivery Period**
  - It will show "El periodo de entrega ha finalizado"
  - If the form was realized it will show "Puntaje: X" or "Puntaje: Sin Registros" if the instructor has not updated it
 
  **Else**
  - If the student enters for the first time or the form is changed in Studio, the test will be created and will only show the form button
  - If the form has already been completed, it will show "Ya realizó este formulario" and it will show the score or "Puntaje: Sin Registros" if the instructor has not updated it
