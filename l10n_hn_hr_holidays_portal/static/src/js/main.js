odoo.define('hr_holidays_portal.javascript', function (require) {
    "use strict";

    const { Component } = owl;
    const { useState } = owl.hooks;
    const { xml } = owl.tags;
    const ajax = require('web.ajax');
    const Dialog = require('web.Dialog');
    const rpc = require('web.rpc');
    const _t = require('web.core')._t;

//    var core = require('web.core');
//    var odoo = require('web.ajax');
//    var Dialog = require('web.Dialog');
//    var rpc = require('web.rpc');
//    var _t = core._t;
//    var ajax = require('web.ajax');

    var MAX_FILE_SIZE = 1024 * 1024; // 5MB

    // For My profile page Models to create Applicant Details
    $(document).ready(function () {
        if ($('.post_active').val()) {
            $('.post-job-menu').css({"color": "rgba(0, 0, 0, 0.9)"})
        }

//        $('#date_from').datepicker({});
//
//        $('#date_to').datepicker({});

        $('.date_from-leave').change(function () {
            var target = $(this).parents('.o_sign_portal');
            var employee_id = $("#employee_id").val();
            var from_date_val = new Date(target.find("input[name='date_from']").val());
            var to_date_val = new Date(target.find("input[name='date_to']").val());
            var leave_type_id = $("#leave_type_id").val();
            var curr_date = new Date();

            console.log("Fecha fin" + to_date_val);
            if (from_date_val < curr_date) {
                alertify.alert()
                    .setting({
                        'label': _t('Alerta'),
                        'title': _t('Error en fecha de inicio'),
                        'message': _t('Por favor la fecha de inicio debe ser mayor que la actual!'),
                        'onok': function () {
                            alertify.success(_t('Gracias'));
                        }
                    }).show();
                $(this).val("")
                return false;
            }
            if (to_date_val) {
                if (from_date_val > to_date_val) {
                    alertify.alert()
                        .setting({
                            'label': _t('Alerta'),
                            'title': _t('Error en fecha de inicio'),
                            'message': _t('Por favor la fecha de inicio debe ser menor que la fecha de fin!'),
                            'onok': function () {
                                alertify.success(_t('Gracias'));
                            }
                        }).show();
                    $(this).val("")
                    return false;
                }
            }

            ajax.jsonRpc('/my/leaves/number_of_day', 'call', {
                    'employee_id': employee_id,
                    'date_from': from_date_val,
                    'date_to': to_date_val,
                    'leave_type_id': leave_type_id,
            }).then((data) => {
                var days = data.days;
                var requires_day = data.requires_day;
                var requires_hour = data.requires_hour;
                var _style = 'none';
                if (requires_day == 1){
                    $("#days").val(days);
                    _style = 'block';
                    $(".days_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".days_div").css('display', _style)
                }
                if (requires_hour == 1){
                    $("#hours").val(days);
                    _style = 'block';
                    $(".hours_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".hours_div").css('display', _style)
                }
           });
        });

        $('.date_to-leave').change(function () {
//            alert('entre');
            var target = $(this).parents('.o_sign_portal');
            var employee_id = $("#employee_id").val();
            var from_date_val = new Date(target.find("input[name='date_from']").val());
            var to_date_val = new Date(target.find("input[name='date_to']").val());
            var leave_type_id = $("#leave_type_id").val();

            if (from_date_val) {
                if (to_date_val < from_date_val) {
                    alertify.alert()
                        .setting({
                            'label': _t('Alerta'),
                            'title': _t('Error en fecha de inicio'),
                            'message': _t('Por favor la fecha de fin debe ser mayor que la fecha de inicio!'),
                            'onok': function () {
                                alertify.success(_t('Gracias'));
                            }
                        }).show();
                    $(this).val("")
                    return false;
                }
            } else {
                alertify.alert()
                    .setting({
                        'label': _t('Alerta'),
                        'title': _t('Error en fecha de inicio'),
                        'message': _t('Por favor debe especificar la fecha de inicio!'),
                        'onok': function () {
                            alertify.success(_t('Gracias'));
                        }
                    }).show();
                $(this).val("")
                return false;
            }

            ajax.jsonRpc('/my/leaves/number_of_day', 'call', {
                    'employee_id': employee_id,
                    'date_from': from_date_val,
                    'date_to': to_date_val,
                    'leave_type_id': leave_type_id,
            }).then((data) => {
                var days = data.days;
                var requires_day = data.requires_day;
                var requires_hour = data.requires_hour;
                var _style = 'none';
                if (requires_day == 1){
                    $("#days").val(days);
                    _style = 'block';
                    $(".days_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".days_div").css('display', _style)
                }
                if (requires_hour == 1){
                   $("#hours").val(days);
                    _style = 'block';
                    $(".hours_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".hours_div").css('display', _style)
                }
            });
        });

        $(".only_number").keypress(function (e) {
            if (e.which != 8 && e.which != 0 && (e.which < 48 || e.which > 57)) {
                return false;
            }
        });

        $("#leave_type_id").change(function () {
            // alert('entre');
            var leave_type_id = $(this).val();
            var employee_id = $("#employee_id").val();
            var target = $(this).parents('.o_sign_portal');
            var from_date_val = new Date(target.find("input[name='date_from']").val());
            var to_date_val = new Date(target.find("input[name='date_to']").val());
            var leave_type_id = $("#leave_type_id").val();

            ajax.jsonRpc('/my/leaves/allocation', 'call', {
                    'employee_id': employee_id,
                    'leave_type_id': leave_type_id,
            }).then((data) => {
                var days = data.days;
                var requires = data.requires;
                $("#allocation").val(days);
                var _style = 'none';
                if (requires == 1){
                    _style = 'block';
                }
                $(".allocation_div").css('display', _style)

            });
            ajax.jsonRpc('/my/leaves/number_of_day', 'call', {
                    'employee_id': employee_id,
                    'date_from': from_date_val,
                    'date_to': to_date_val,
                    'leave_type_id': leave_type_id,
            }).then((data) => {
                var days = data.days;
                var requires_day = data.requires_day;
                var requires_hour = data.requires_hour;
                var _style = 'none';
                if (requires_day == 1){
                    $("#days").val(days);
                    _style = 'block';
                    $(".days_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".days_div").css('display', _style)
                }
                if (requires_hour == 1){
                    $("#hours").val(days);
                    _style = 'block';
                    $(".hours_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".hours_div").css('display', _style)
                }

           });
            });

    });

    $(document).ready(function () {
        $('#top_menu li').addClass('job_portal_menus')
        $('.job_portal_menus').each(function () {

            if ($.trim($(this).text()) == 'Post Job') {
                $(this).attr('groups', 'base.group_erp_manager')
            }
        })


        // Get formatted date YYYY-MM-DD
        function getFormattedDate(date) {
            return date.getFullYear()
                + "-"
                + ("0" + (date.getMonth() + 1)).slice(-2)
                + "-"
                + ("0" + date.getDate()).slice(-2);
        }



        $('input.js_select_language').select2({
            tags: true,
            tokenSeparators: [",", " ", "_"],
            maximumInputLength: 35,
            minimumInputLength: 2,
            maximumSelectionSize: 5,
            lastsearch: [],
            ajax: {
                url: '/l10n_cu_hr_recruitment/get_language',
                dataType: 'json',
                data: function (term) {
                    return {
                        q: term,
                        l: 50
                    };
                },
                results: function (data) {
                    var ret = [];
                    _.each(data, function (x) {
                        ret.push({id: x.id, text: x.name, isNew: false});
                    });
                    return {results: ret};
                }
            },
            // Take default tags from the input value
            initSelection: function (element, callback) {
                var data = [];
                _.each(element.data('init-value'), function (x) {
                    data.push({id: x.id, text: x.name, isNew: false});
                });
                element.val('');
                callback(data);
            },
        });

        // For Industry Practices Static Page JS
        $("div.bhoechie-tab-menu>div.list-group>a").click(function (e) {
            e.stopPropagation();
            e.preventDefault();
            $(this).siblings('a.active').removeClass("active");
            $(this).addClass("active");
            var index = $(this).index();
            $("div.bhoechie-tab>div.bhoechie-tab-content").removeClass("active");
            $("div.bhoechie-tab>div.bhoechie-tab-content").eq(index).addClass("active");
        });

        $('#uploadFile').change(function () {
            var fileSize = this.files[0].size;
            if (fileSize > MAX_FILE_SIZE) {
                this.setCustomValidity("El fichero no puede exceder de 1MB!");
                this.reportValidity();
                this.value = '';
            } else {
                this.setCustomValidity("");
            }
        });
    });
});
