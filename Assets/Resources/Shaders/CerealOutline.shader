// URP-compatible inverted-hull outline. Unity uses HLSL (not GLSL) for URP shaders.
Shader "Custom/CerealOutline"
{
    Properties
    {
        _OutlineColor ("Outline Color", Color) = (1,1,1,1)
        _OutlineScale ("Outline Scale", Float) = 0.06
        _PivotOS ("Scale Pivot (object space)", Vector) = (0,0,0,0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry+1" }
        Pass
        {
            Name "Outline"
            Tags { "LightMode"="UniversalForward" }
            Cull Front
            ZWrite On
            ZTest LEqual

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _OutlineColor;
                float _OutlineScale;
                float4 _PivotOS;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings   { float4 positionCS : SV_POSITION; };

            Varyings vert(Attributes IN)
            {
                Varyings OUT;
                // Scale the mesh away from its center: works well for box-shaped meshes
                // (normal extrusion would tear apart at hard-edged cube corners).
                float3 p = _PivotOS.xyz + (IN.positionOS.xyz - _PivotOS.xyz) * (1.0 + _OutlineScale);
                OUT.positionCS = TransformObjectToHClip(p);
                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target { return _OutlineColor; }
            ENDHLSL
        }
    }
}
