/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";

patch(publicWidget.registry.hrRecruitment.prototype, {
    /**
     * @override
     */
    events: {
        ...publicWidget.registry.hrRecruitment.prototype.events,

        'input #recruitment3': '_onInputPhone',
        'focusout #recruitment13': '_onFocusOutIdentification',
        'input #recruitment13': '_onInputIdentification',
        'focusout #recruitment19': '_onFocusOutExpectedSalary',
        'input #recruitment19': '_onInputExpectedSalary',
        'change #recruitment14': '_onChangeCountry',
        'change #recruitment15': '_onChangeState',
    },

    /**
     * @override
     */
    init() {
        super.init(...arguments);
        this.states = [];
        this.countries = [];
        this.hn_country_id = 0;
        this.applied_same_job_email = false;
        this.applied_same_job_identification = false;
    },

    /**
     * @override
     */
    async willStart() {
        return Promise.all([
            this._loadCountries(),
        ]);
    },

    async _loadCountries() {
        const countries = await this.rpc('/website_hr_recruitment/get_countries');
        this.countries = countries;
        this.hn_country_id = this.countries.find(country => country.code === 'HN').id;
        await this._loadStates(this.hn_country_id);
        // this.$el.find('#recruitment14').select2({
        //     placeholder: _t('Select a country'),
        //     allowClear: true,
        //     data: countries.map(country => {
        //         return {
        //             id: country.id,
        //             text: country.name,
        //         };
        //     }),
        // });

        // this.$el.find('#recruitment14').val(hn_id).trigger('change');
    },

    async _loadStates(country_id) {
        if (!country_id) {
            this.states = [];
        }

        if (country_id) {
            const states = await this.rpc('/website_hr_recruitment/get_states', { country_id: country_id, });
            this.states = states;
        }

        this.updateState();
    },

    async _onChangeCountry(ev) {
        const country_id = $(ev.currentTarget).val();
        await this._loadStates(country_id);

        // if (!country_id) {
        //     this.$el.find('#recruitment15_field').hide();
        // }
        // else {
        //     this.$el.find('#recruitment15_field').show();
        // }
    },

    async updateState() {
        const placeholder = _t('Select a state');
        this.$el.find('#recruitment15').select2({
            placeholder: placeholder,
            allowClear: true,
            data: this.states.map(state => {
                return {
                    id: state.id,
                    text: state.name,
                };
            }),
        });
    },

    // State
    async _onChangeState(ev) {
        const state_id = $(ev.currentTarget).val();
        
        $('#state-message').removeClass('alert-danger').hide();
        $(ev.currentTarget).removeClass('border-danger');

        // Reset button
        $('#apply-btn').removeClass('disabled') // !compatibility
        .removeAttr('disabled');

        if (!state_id) {
            $(ev.currentTarget).addClass('border-danger');
            $('#state-message').text(_t("The state is required.")).addClass('alert-danger').show();
            $('#apply-btn').addClass('disabled') // !compatibility
        }
    },

    // Phone
    async _onInputPhone(ev) {
        var phone = $(ev.currentTarget).val();
        phone = phone.replace(/[^0-9]/g, '');

        $(ev.currentTarget).val(phone);
    },
    

    // Identification
    async _onInputIdentification(ev) {
        var identification = $(ev.currentTarget).val();
        identification = identification.replace(/[^0-9]/g, '');

        $(ev.currentTarget).val(identification);
    },

    async _onFocusOutIdentification(ev) {
        const identification = $(ev.currentTarget).val()
        // Reset message
        $('#identification-message').removeClass('alert-warning').hide();
        $(ev.currentTarget).removeClass('border-warning');

        // Reset button
        $('#apply-btn').removeClass('disabled') // !compatibility
        .removeAttr('disabled');
        
        // Validate length
        if (identification.length != 13) {
            $(ev.currentTarget).addClass('border-warning');
            $('#identification-message').text(_t("The value entered doesn't seems like a valid identification number.")).addClass('alert-warning').show();
            $('#apply-btn').addClass('disabled') // !compatibility
            .attr('disabled', 'disabled');
            return;
        }

        const job_id = $('#recruitment7').val();
        const data = await this.rpc('/website_hr_recruitment/check_recent_application_by_id',
        {
            identification_id: identification,
            job_id: job_id,
        });
        this.applied_same_job_identification = data.applied_same_job;
        if(data.applied_same_job) {
            $('#identification-message').removeClass('alert-warning').hide();
            $(ev.currentTarget).addClass('border-warning');
            $('#identification-message').text(_t("You already applied to this job position recently.")).addClass('alert-warning').show();
            $('#apply-btn').addClass('disabled') // !compatibility
            .attr('disabled', 'disabled');
        } else if(data.applied_other_job) {
            $('#identification-message').removeClass('alert-warning').hide();
            $(ev.currentTarget).addClass('border-warning');
            $('#identification-message').text(_t("You already applied to another position recently. You can continue if it's not a mistake.")).addClass('alert-warning').show();
        }
    },

    // Expected Salary
    async _onFocusOutExpectedSalary(ev) {
        var salary = $(ev.currentTarget).val()
        if (!salary) {
            salary = 0;
        }
        const new_salary = parseFloat(salary).toFixed(2);
        $(ev.currentTarget).val(new_salary);

    },

    async _onInputExpectedSalary(ev) {
        var salary = $(ev.currentTarget).val();
        salary = salary.replace(/[^0-9.]/g, '');
        if (salary.split('.').length > 2) {
            salary = salary.slice(0, -1);
        }
        $(ev.currentTarget).val(salary);
    },

    /**
     * @override
     */
    _onClickApplyButton (ev) {
        ev.preventDefault();

        super._onClickApplyButton(...arguments);

        // CV and LinkedIn not required
        const $linkedin_profile = $('#recruitment4');
        const $resume = $('#recruitment6');
        const $recruitment15 = $('#recruitment15');

        if ($recruitment15.val() == '') {
            $('#state-message').text(_t("The state is required.")).addClass('alert-danger').show();
            $recruitment15.addClass('border-danger');
            return;
        }

        $linkedin_profile.attr('required', false);
        $resume.attr('required', false);

  
        $('input[required], select[required], textarea[required], checkbox[required]').each(function() {
            if (!$(this).val()) {
                $(this).focus();
            }
        });

        

        if (this.applied_same_job_email || this.applied_same_job_identification) {
            if(this.applied_same_job_email) {
                $('#recruitment2').focus();
            }
            if(this.applied_same_job_identification) {
                $('#recruitment13').focus();
            }
            window.location = window.location;
        }
    
        this.$el.removeClass('o_has_error').find('.form-control').removeClass('is-invalid');
    },

    /**
     * @override
     */
    async _onFocusOutMail (ev) {
        super._onFocusOutMail(...arguments);
        const email = $(ev.currentTarget).val();

        const job_id = $('#recruitment7').val();
        const data = await this.rpc('/website_hr_recruitment/check_recent_application',
            {
                email: email,
                job_id: job_id,
            });

        this.applied_same_job_email = data.applied_same_job
        if (data.applied_same_job) {
            $('#apply-btn').addClass('disabled') // !compatibility
            .attr('disabled', 'disabled');
        }
    },

});
