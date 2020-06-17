/*
        .-"-.
       /|6 6|\
      {/(_0_)\}
       _/ ^ \_
      (/ /^\ \)-'
       ""' '""
*/


function EolTimifyXBlock(runtime, element) {

    $(element).find('.save-button-eoltimify').bind('click', function(eventObject) {
        eventObject.preventDefault();
        var handlerUrl = runtime.handlerUrl(element, 'studio_submit');

        var data = {
            'display_name': $(element).find('input[name=display_name]').val(),
            'duration': $(element).find('input[name=duration]').val(),
            'autoclose': $(element).find('select[name=timifyautoclose]').val(),
            'idform': $(element).find('select[name=timifyform]').val()
        };
        
        if ($.isFunction(runtime.notify)) {
            runtime.notify('save', {state: 'start'});
        }
        $.post(handlerUrl, JSON.stringify(data)).done(function(response) {
            if (response.result == 'success' && $.isFunction(runtime.notify)) {
                runtime.notify('save', {state: 'end'});
            }
            else {
                runtime.notify('error',  {
                    title: 'Error: Falló en Guardar',
                    message: 'Revise los campos si estan correctos.'
                });
            }
        });
    });
    
    $(element).find('.cancel-button-eoltimify').bind('click', function(eventObject) {
        eventObject.preventDefault();
        runtime.notify('cancel', {});
    });

}