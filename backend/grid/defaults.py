from copy import deepcopy

STUDY = 'https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/joe.2017.0447'
DEFAULTS = {
    'solar': {'capacity_kw': 600, 'tilt': 27, 'azimuth': 180, 'derating': .9, 'inverter_efficiency': .96, 'provenance': 'study'},
    'wind': {'capacity_kw': 100, 'hub_height_m': 30, 'cut_in': 3, 'rated_speed': 12, 'cut_out': 25, 'shear_exponent': .14, 'provenance': 'study'},
    'battery': {'capacity_kwh': 3000, 'min_soc': 20, 'max_soc': 95, 'reserve_soc': 30, 'max_charge_kw': 200,
                'max_discharge_kw': 200, 'charge_efficiency': .95, 'discharge_efficiency': .95,
                'replacement_cost': 30000000, 'lifetime_throughput_kwh': 9000000, 'provenance': 'study'},
    'generator': {'capacity_kw': 200, 'min_power_kw': 40, 'fuel_slope': .246, 'fuel_intercept': 10.5,
                  'start_cost': 0, 'diesel_price': 90, 'available_fuel_l': 500, 'emissions_factor': 2.68,
                  'min_up_hours': 1, 'min_down_hours': 1, 'ramp_kw_per_hour': 200, 'provenance': 'study'},
    'policy': {'critical_target_pct': 100, 'renewable_target_pct': 70, 'terminal_soc': 30,
               'allowed_generator_hours': list(range(24)), 'max_starts': 6,
               'curtailment_penalty': .01, 'renewable_shortfall_penalty': 1, 'provenance': 'operator'},
    'demand': {'daily_kwh': 876.41, 'peak_kw': 101, 'critical_pct': 30, 'flexible_pct': 10,
               'provenance': 'simulated_from_published_totals'},
    'flexible_loads': [{'name': 'Community water pumping (assumed)', 'power_kw': 15, 'required_kwh': 87.641,
                        'start_hour': 9, 'end_hour': 17, 'priority': 'flexible', 'provenance': 'simulated'}],
}


def default_configuration():
    return deepcopy(DEFAULTS)


def daily_shape(daily_kwh, peak_kw):
    # Fix the 18:00 peak first, then distribute the remaining energy exactly.
    weights = [.18,.15,.14,.13,.14,.20,.35,.50,.45,.36,.32,.30,.28,.27,.28,.32,.42,.65,1,.95,.75,.52,.36,.25]
    weights[18] = 0
    values = [v * (daily_kwh - peak_kw) / sum(weights) for v in weights]
    # Water filling handles user totals near 24 * peak without exceeding peak.
    active = list(range(24))
    active.remove(18)
    remaining = daily_kwh - peak_kw
    while active:
        denom = sum(weights[i] for i in active)
        proposed = {i: remaining * weights[i] / denom for i in active}
        capped = [i for i, v in proposed.items() if v > peak_kw]
        if not capped:
            for i, v in proposed.items(): values[i] = v
            break
        for i in capped:
            values[i] = peak_kw
            remaining -= peak_kw
            active.remove(i)
    values[18] = peak_kw
    return values
