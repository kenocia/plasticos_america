/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ExpenseForm extends Component {
    static template = "hr_hn_portal_expense.ExpenseFormTemplate";
    
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            expenseList: [],
            currentExpense: {
                name: '',
                description: '',
                date: '',
                payment_mode: '',
                quantity: '',
                total_amount_currency: '',
                product_id: '',
                archivo_adjunto: []
            },
            showQuantity: false,
            unitPrice: 0,
            errors: {},
            isMultiple: false
        });
        
        this.formRef = useRef("form");
    }

    async onProductChange(ev) {
        const productId = ev.target.value;
        if (productId) {
            try {
                const product = await this.rpc("/get_value_of_product", {
                    product_id: productId,
                });
                
                this.state.showQuantity = product.quantity || false;
                this.state.unitPrice = product.unit_price || 0;
                
                if (this.state.showQuantity) {
                    this.state.currentExpense.quantity = '1';
                    this.calculateTotal();
                }
            } catch (error) {
                console.error("Error fetching product:", error);
            }
        }
    }

    onQuantityChange(ev) {
        this.state.currentExpense.quantity = ev.target.value;
        this.calculateTotal();
    }

    calculateTotal() {
        if (this.state.showQuantity && this.state.currentExpense.quantity) {
            const qty = parseFloat(this.state.currentExpense.quantity) || 0;
            this.state.currentExpense.total_amount_currency = (this.state.unitPrice * qty).toFixed(2);
        }
    }

    validateExpense(expense) {
        const errors = {};
        
        if (!expense.name.trim()) {
            errors.name = "Debe llenar este campo";
        }
        
        if (!expense.description.trim()) {
            errors.description = "Debe llenar este campo";
        }
        
        if (!expense.date) {
            errors.date = "Debe llenar este campo";
        }
        
        if (!expense.payment_mode) {
            errors.payment_mode = "Debe seleccionar uno de los valores de este campo";
        }
        
        if (this.state.showQuantity && !expense.quantity) {
            errors.quantity = "Debe llenar este campo";
        }
        
        if (!expense.total_amount_currency) {
            errors.total_amount_currency = "Debe llenar este campo";
        }
        
        this.state.errors = errors;
        return Object.keys(errors).length === 0;
    }

    async onSaveAndNew(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        if (this.validateExpense(this.state.currentExpense)) {
            // Procesar archivos adjuntos
            const fileInput = this.formRef.el.querySelector('#archivo_adjunto');
            const files = Array.from(fileInput.files);
            const fileArray = [];
            
            for (const file of files) {
                const base64 = await this.fileToBase64(file);
                fileArray.push({
                    data: base64,
                    name: file.name,
                    type: file.type
                });
            }
            
            const expenseToAdd = {
                ...this.state.currentExpense,
                archivo_adjunto: fileArray
            };
            
            this.state.expenseList.push(expenseToAdd);
            this.clearForm();
        }
    }

    async onSaveAll(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        if (this.validateExpense(this.state.currentExpense)) {
            // Agregar el último gasto si es válido
            const fileInput = this.formRef.el.querySelector('#archivo_adjunto');
            const files = Array.from(fileInput.files);
            const fileArray = [];
            
            for (const file of files) {
                const base64 = await this.fileToBase64(file);
                fileArray.push({
                    data: base64,
                    name: file.name,
                    type: file.type
                });
            }
            
            const expenseToAdd = {
                ...this.state.currentExpense,
                archivo_adjunto: fileArray
            };
            
            this.state.expenseList.push(expenseToAdd);
            
            try {
                await this.rpc("/safe_hr_expense", {
                    expense_list: this.state.expenseList,
                });
                
                window.location.href = '/expense/answer_form';
            } catch (error) {
                console.error("Error saving expenses:", error);
            }
        }
    }

    removeFromList(index) {
        this.state.expenseList.splice(index, 1);
    }

    clearForm() {
        this.state.currentExpense = {
            name: '',
            description: '',
            date: '',
            payment_mode: '',
            quantity: '',
            total_amount_currency: '',
            product_id: '',
            archivo_adjunto: []
        };
        this.state.errors = {};
        this.state.showQuantity = false;
        this.state.unitPrice = 0;
        
        // Limpiar el formulario HTML
        const form = this.formRef.el;
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (input.type === 'file') {
                input.value = '';
            } else if (input.type === 'radio' || input.type === 'checkbox') {
                input.checked = false;
            } else {
                input.value = '';
            }
        });
    }

    fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
        });
    }
}
