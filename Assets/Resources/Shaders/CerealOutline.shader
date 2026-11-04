// Built-in render pipeline inverted-hull outline (written in CG, which Unity compiles for DX/GL/Metal).
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
        Tags { "RenderType"="Opaque" "Queue"="Geometry+1" }
        Pass
        {
            Name "Outline"
            Cull Front
            ZWrite On
            ZTest LEqual

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            fixed4 _OutlineColor;
            float _OutlineScale;
            float4 _PivotOS;

            struct appdata { float4 vertex : POSITION; };
            struct v2f { float4 pos : SV_POSITION; };

            v2f vert(appdata v)
            {
                v2f o;
                // Scale the mesh away from its center: works for box-shaped meshes
                // (normal extrusion tears apart at hard-edged cube corners).
                float3 p = _PivotOS.xyz + (v.vertex.xyz - _PivotOS.xyz) * (1.0 + _OutlineScale);
                o.pos = UnityObjectToClipPos(float4(p, 1.0));
                return o;
            }

            fixed4 frag(v2f i) : SV_Target { return _OutlineColor; }
            ENDCG
        }
    }
}
