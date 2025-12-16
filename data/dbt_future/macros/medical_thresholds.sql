-- Macro pour calculer les seuils d'alerte personnalisés par âge et génotype
-- Utilisée dans plusieurs modèles pour la cohérence

{% macro get_medical_thresholds(age_years, genotype, metric_type) %}
  CASE
    {% if metric_type == 'spo2' %}
      WHEN '{{ genotype }}' = 'SS' AND {{ age_years }} < 5 THEN 92  -- Plus strict pour SS jeunes
      WHEN '{{ genotype }}' = 'SS' THEN 90
      WHEN '{{ genotype }}' IN ('SC', 'Sβ0') THEN 88
      ELSE 90
    {% elif metric_type == 'heart_rate_max' %}
      WHEN {{ age_years }} < 1 THEN 160
      WHEN {{ age_years }} BETWEEN 1 AND 5 THEN 130
      WHEN {{ age_years }} BETWEEN 6 AND 10 THEN 120
      WHEN {{ age_years }} BETWEEN 11 AND 15 THEN 110
      ELSE 100
    {% elif metric_type == 'heart_rate_min' %}
      WHEN {{ age_years }} < 1 THEN 100
      WHEN {{ age_years }} BETWEEN 1 AND 10 THEN 70
      ELSE 60
    {% elif metric_type == 'fever_threshold' %}
      WHEN {{ age_years }} < 3 THEN 37.8  -- Plus sensible pour les jeunes enfants
      ELSE 38.0
    {% endif %}
  END
{% endmacro %}
