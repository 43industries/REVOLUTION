shader_type spatial;
render_mode cull_back, ambient_light_disabled;

uniform vec4 albedo : source_color = vec4(0.86, 0.82, 0.75, 1.0);
uniform float hurt_flash : hint_range(0.0, 1.0) = 0.0;
uniform float chronal_rim : hint_range(0.0, 1.0) = 0.0;
uniform float lane_tint : hint_range(0.5, 1.2) = 1.0;
uniform float specular_step : hint_range(0.0, 1.0) = 0.55;
uniform vec3 rim_color : source_color = vec3(0.2, 0.85, 1.0);
uniform float shadow_band : hint_range(0.0, 1.0) = 0.35;
uniform float mid_band : hint_range(0.0, 1.0) = 0.7;
uniform vec3 light_dir = vec3(0.4, 0.85, 0.35);

void fragment() {
	vec3 n = normalize(NORMAL);
	vec3 l = normalize(light_dir);
	float ndl = clamp(dot(n, l), 0.0, 1.0);

	float shade = 0.35;
	if (ndl > mid_band) {
		shade = 1.0;
	} else if (ndl > shadow_band) {
		shade = 0.65;
	}

	float spec = 0.0;
	if (ndl > specular_step) {
		spec = 0.22;
	}

	vec3 base = albedo.rgb * lane_tint * shade + vec3(spec);
	base = mix(base, vec3(1.0, 0.35, 0.3), hurt_flash);

	float fres = pow(1.0 - clamp(dot(n, VIEW), 0.0, 1.0), 2.5);
	base += rim_color * chronal_rim * fres * 1.4;

	ALBEDO = base;
	ROUGHNESS = 1.0;
	METALLIC = 0.0;
	EMISSION = rim_color * chronal_rim * 0.4;
}
