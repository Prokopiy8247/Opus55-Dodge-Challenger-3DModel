// Deformation heat-map on the visual mesh (brief 16): colour by the displacement of each vertex from where the undeformed
// car would put it, i.e. the vertex's model-pose position (UV3, written by the car importer) carried by the rigid frame of
// the cabin floor (_HellcatBodyFrame, set per frame by DebugViews). Blue 0 -> cyan -> green -> yellow -> red at _Range
// metres -> magenta beyond; simple wrap lighting keeps the shape readable.
Shader "Hellcat/DeformationHeatmap"
{
    Properties
    {
        _Range ("Red at (m)", Float) = 0.3
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }
        Pass
        {
            Name "Heatmap"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float _Range;
            CBUFFER_END
            float4x4 _HellcatBodyFrame;   // car model frame -> world (rigid fit of the cabin floor)

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 rest : TEXCOORD3;   // model-pose position (car frame)
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 normalWS : TEXCOORD0;
                float disp : TEXCOORD1;
            };

            Varyings vert(Attributes v)
            {
                Varyings o;
                float3 ws = TransformObjectToWorld(v.positionOS.xyz);
                float3 expected = mul(_HellcatBodyFrame, float4(v.rest.xyz, 1.0)).xyz;
                o.disp = distance(ws, expected);
                o.positionCS = TransformWorldToHClip(ws);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }

            float3 Ramp(float t)
            {
                const float3 c0 = float3(0.08, 0.16, 0.75);
                const float3 c1 = float3(0.00, 0.70, 0.95);
                const float3 c2 = float3(0.20, 0.85, 0.25);
                const float3 c3 = float3(1.00, 0.88, 0.10);
                const float3 c4 = float3(1.00, 0.12, 0.05);
                const float3 c5 = float3(0.85, 0.00, 0.65);
                if (t < 0.15) return lerp(c0, c1, t / 0.15);
                if (t < 0.35) return lerp(c1, c2, (t - 0.15) / 0.20);
                if (t < 0.60) return lerp(c2, c3, (t - 0.35) / 0.25);
                if (t < 1.00) return lerp(c3, c4, (t - 0.60) / 0.40);
                return lerp(c4, c5, saturate(t - 1.0));
            }

            half4 frag(Varyings i, bool front : SV_IsFrontFace) : SV_Target
            {
                float t = i.disp / max(_Range, 1e-4);
                float3 c = Ramp(t);
                float3 n = normalize(i.normalWS) * (front ? 1.0 : -1.0);
                Light l = GetMainLight();
                float lit = 0.35 + 0.65 * saturate(dot(n, l.direction) * 0.5 + 0.5);
                return half4(c * lit, 1.0);
            }
            ENDHLSL
        }
    }
}
