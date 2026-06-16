odoo.define('l10n_cu_hr_recruitment_fgne.grid_editable', function () {

    var classificationOptions = [
        'Lenguages',
        'Herramientas de pruebas',
        'Tecnologías',
        'Metodologías',
        'Control de versiones',
    ];

    $(document).ready(function () {

        var columnDefs = [
            {
                data: "id",
                title: "Id",
                type: "hidden",
                visible: false,
            },
            {
                data: "clasification",
                title: "Clasificaciones",
                type: "select",
                options: classificationOptions,
                select2: {width: "100%"},
                editorOnChange: function (event, altEditor) {
                    console.log(event, altEditor);
                    var clasification = $(event.currentTarget).val();
                    var dict = {
                        'value': clasification,
                    };
                    $(altEditor.modal_selector).find("#alteditor-row-town").show();
                    $.ajax({
                        url: '/get_esp',
                        type: 'GET',
                        data: dict,
                        success: function (options) {
                            console.log(options);
                            options = JSON.parse(options);
                            var esp = $(altEditor.modal_selector).find('#esp');
                            altEditor.reloadOptions(esp, options);
                        }
                    });
                }
            },
            {
                data: "esp",
                title: "Específico",
                type: "select",
                select2: {width: "100%"}
            }


        ];

        var myTable;

        // local URL's are not allowed
        var get_items = '/get_items';
        var add_items = '/add_items';
        var url_ws_mock_ok = '/save/document';

        var div_order = $(this).find('.s_website_form');

        myTable = $('#example').DataTable({
            initComplete: function () {
                $(this.api().table().container()).find('input').parent().wrap('<form>').parent().attr('autocomplete', 'off');
            },

            "sPaginationType": "full_numbers",
            ajax: {
                "url": get_items,
                "type": 'POST',
                "data": {
                    "SaleOrderId": div_order[0].dataset.orderId,
                }
            },
            columns: columnDefs,
            dom: 'Bfrtip',        // Needs button container
            select: 'single',
            responsive: true,
            altEditor: true,
            autoFill: false,
            buttons: [
                {
                    text: 'Adicionar',
                    name: 'add'        // do not change name
                },
            ],
            onAddRow: function (datatable, rowdata, success, error) {
                $.ajax({
                    // a tipycal url would be / with type='PUT'
                    url: add_items,
                    type: 'GET',
                    data: rowdata,
                    success: success,
                    error: error
                });
            },

        });
    });
});