-- Macro pour la pseudonymisation conforme GDPR
-- Anonymise les données patients sensibles pour les rapports

{% macro pseudonymize_patient_data(column_name, patient_id_col='patient_id') %}
  {% if var('enable_pseudonymization') %}
    MD5(CONCAT({{ column_name }}, '{{ var("pseudonym_salt") }}', {{ patient_id_col }}))
  {% else %}
    {{ column_name }}
  {% endif %}
{% endmacro %}

-- Macro pour calculer les fenêtres temporelles médicales
{% macro medical_time_windows(timestamp_col, window_type='daily') %}
  {% if window_type == 'shift' %}
    -- Fenêtres de garde médicale (8h, 16h, 24h)
    CASE
      WHEN EXTRACT(HOUR FROM {{ timestamp_col }}) BETWEEN 7 AND 14 THEN 'morning_shift'
      WHEN EXTRACT(HOUR FROM {{ timestamp_col }}) BETWEEN 15 AND 22 THEN 'afternoon_shift'
      ELSE 'night_shift'
    END
  {% elif window_type == 'daily' %}
    DATE_TRUNC('day', {{ timestamp_col }})
  {% elif window_type == 'weekly' %}
    DATE_TRUNC('week', {{ timestamp_col }})
  {% elif window_type == 'hourly' %}
    DATE_TRUNC('hour', {{ timestamp_col }})
  {% endif %}
{% endmacro %}

-- Macro pour détecter les crises de drépanocytose
{% macro detect_sickle_cell_crisis(spo2_col, temp_col, pain_level_col=none) %}
  CASE
    WHEN {{ spo2_col }} < 90
         AND {{ temp_col }} > 38.0
         {% if pain_level_col %}AND {{ pain_level_col }} > 7{% endif %}
    THEN 'ACUTE_CRISIS'

    WHEN {{ spo2_col }} < 92
         AND {{ temp_col }} > 37.8
    THEN 'WARNING_SIGNS'

    ELSE 'STABLE'
  END
{% endmacro %}
