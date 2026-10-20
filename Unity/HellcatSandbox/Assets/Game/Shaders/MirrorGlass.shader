// Mirror glass (D-021): the mirror camera's render texture mapped across the pane in the mirror's own frame, flipped left
// to right (a mirror shows the scene behind the driver mirrored). _MirrorRight / _MirrorUp are the pane axes divided by its
// width / height (world space), set per frame by CockpitInstruments.
Shader "Hellcat/MirrorGlass"
{
    Properties
    {
        _MirrorTex ("Mirror", 2D) = "black" {}
        _Tint ("Tint", Color) = (0.86, 0.88, 0.9, 1)
        [HideInInspector] _MirrorCentre ("Centre", Vector) = (0, 0, 0, 0)
        [HideInInspector] _MirrorRight ("Right / width", Vector) = (1, 0, 0, 0)
        [HideInInspector] _MirrorUp ("Up / height", Vector) = (0, 1, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }
        Pass
        {
            Name "MirrorGlass"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MirrorTex);
            SAMPLER(sampler_MirrorTex);
            CBUFFER_START(UnityPerMaterial)
                float4 _MirrorTex_ST;
                float4 _Tint;
                float4 _MirrorCentre;
                float4 _MirrorRight;
                float4 _MirrorUp;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                float3 d = i.positionWS - _MirrorCentre.xyz;
                float2 uv = float2(0.5 - dot(d, _MirrorRight.xyz), 0.5 + dot(d, _MirrorUp.xyz));
                half3 c = SAMPLE_TEXTURE2D(_MirrorTex, sampler_MirrorTex, saturate(uv)).rgb * _Tint.rgb;
                return half4(c, 1.0);
            }
            ENDHLSL
        }
    }
}
