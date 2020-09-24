/*
        .-"-.
       /|6 6|\
      {/(_0_)\}
       _/ ^ \_
      (/ /^\ \)-'
       ""' '""
*/


function EolTimifyXBlock(runtime, element) {
    var $ = window.jQuery;
    var $element = $(element);
    var handlerUrlShowScore = runtime.handlerUrl(element, 'show_score');
    
    function showScores(result){
        if (result.result == 'success'){
            var lista = result.list_student
            var table = $element.find('#tabla-alumnos')[0]
            for(var i = 0; i < lista.length; i+=1){
                table.innerHTML = table.innerHTML + "<tr><td>"+lista[i][1]+"</td><td>"+lista[i][2]+"</td><td>"+lista[i][3]+"</td><td>"+lista[i][4]+"</td><td>"+lista[i][5]+"</td></tr>"
            };
            $element.find('.eoltimify_scores_instructor')[0].style.visibility = "visible";
        }
        $element.find('#timify_loading_ui').hide()
        $element.find('#quilgo_button')[0].disabled = false
        if (result.result == 'error'){
            $element.find('.eoltimify_error_instructor')[0].innerHTML = "Un error inesperado ha ocurrido, actialice la página e intentelo nuevamente</br>Si el error persiste contactese con el soporte."
        }
        if (result.result == 'error2'){
            $element.find('.eoltimify_error_instructor')[0].innerHTML = "No hay Links creados"
        }
    }
    $('input[name=show]').live('click', function (event) {
        event.currentTarget.disabled = true
        $element.find('#timify_loading_ui').show()
        $.ajax({
            type: "POST",
            url: handlerUrlShowScore,
            data: "{}",
            success: showScores
        });        
    });
}
