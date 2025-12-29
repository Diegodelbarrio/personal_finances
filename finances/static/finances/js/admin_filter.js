// finances/static/finances/js/admin_filter.js
(function($) {
    'use strict';
    $(document).ready(function() {
        // 1. Si cambia el usuario, reseteamos los campos dependientes
        $('#id_user').change(function() {
            $('#id_subcategory').val(null).trigger('change');
            $('#id_location').val(null).trigger('change');
        });

        // 2. Interceptamos la petición de autocompletado (Select2)
        $(document).on('select2:opening', function (e) {
            const userId = $('#id_user').val();
            
            // Si no hay usuario seleccionado, avisamos (opcional)
            if (!userId) {
                return;
            }

            const element = $(e.target);
            const s2 = element.data('select2');
            
            if (s2 && s2.options && s2.options.options && s2.options.options.ajax) {
                // Modificamos los datos que se envían al servidor
                const originalData = s2.options.options.ajax.data;
                s2.options.options.ajax.data = function(params) {
                    const data = originalData(params);
                    data.user_id = userId; // Inyectamos el ID del usuario en la query string
                    return data;
                };
            }
        });
    });
})(django.jQuery);