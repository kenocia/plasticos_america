/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { GraphModel } from "@web/views/graph/graph_model";

const SPC_MEASURE_SPECS = [
    ["measure", "avg"],
    ["spc_chart_norm", "avg"],
    ["tolerance_min", "avg"],
    ["tolerance_max", "avg"],
];

const SPC_SERIES_LABELS = {
    measure: _t("Medida"),
    spc_chart_norm: _t("Norma"),
    tolerance_min: _t("T. mínima"),
    tolerance_max: _t("T. máxima"),
};

patch(GraphModel.prototype, {
    _getDatasetLabel(dataPoint) {
        if (dataPoint.spcSeriesLabel) {
            return dataPoint.spcSeriesLabel;
        }
        return super._getDatasetLabel(...arguments);
    },

    async _loadDataPoints(metaData) {
        const ctx = metaData.context || {};
        if (!ctx.graph_spc_limits || metaData.mode !== "line") {
            return super._loadDataPoints(...arguments);
        }

        const { domains, fields, groupBy, resModel } = metaData;
        const readMeasures = ["__count", ...SPC_MEASURE_SPECS.map(([f, op]) => `${f}:${op}`)];

        const proms = domains.map(async (domain, originIndex) => {
            const numbering = {};
            const data = await this.orm.webReadGroup(
                resModel,
                domain.arrayRepr,
                readMeasures,
                groupBy.map((gb) => gb.spec),
                {
                    lazy: false,
                    context: { fill_temporal: true, ...this.searchParams.context },
                }
            );
            const dataPoints = [];
            for (const group of data.groups) {
                const { __domain, __count } = group;
                const labels = [];
                const rawValues = [];
                for (const gb of groupBy) {
                    let label;
                    const val = group[gb.spec];
                    rawValues.push({ [gb.spec]: val });
                    const fieldName = gb.fieldName;
                    const { type } = fields[fieldName];
                    if (type === "boolean") {
                        label = `${val}`;
                    } else if (val === false) {
                        label = this._getDefaultFilterLabel(gb);
                    } else if (["many2many", "many2one"].includes(type)) {
                        const [id, name] = val;
                        const key = JSON.stringify([fieldName, name]);
                        if (!numbering[key]) {
                            numbering[key] = {};
                        }
                        const numbers = numbering[key];
                        if (!numbers[id]) {
                            numbers[id] = Object.keys(numbers).length + 1;
                        }
                        const num = numbers[id];
                        label = num === 1 ? name : `${name} (${num})`;
                    } else if (type === "selection") {
                        const selected = fields[fieldName].selection.find((s) => s[0] === val);
                        label = selected ? selected[1] : val;
                    } else {
                        label = val;
                    }
                    labels.push(label);
                }

                for (const [fname] of SPC_MEASURE_SPECS) {
                    let value = group[fname];
                    if (value instanceof Array) {
                        value = 1;
                    }
                    if (value !== undefined && value !== null && !Number.isInteger(value)) {
                        metaData.allIntegers = false;
                    }
                    dataPoints.push({
                        count: __count,
                        domain: __domain,
                        value,
                        labels,
                        originIndex,
                        identifier: JSON.stringify([...rawValues, fname]),
                        cumulatedStart: 0,
                        spcSeriesLabel: SPC_SERIES_LABELS[fname] || fname,
                    });
                }
            }
            return dataPoints;
        });
        const promResults = await Promise.all(proms);
        return promResults.flat();
    },
});
