Shader "Unlit/OutlineHLSL"
{
    Properties
    {
        _Color ("Color", Color) = (0,0,0,1)
        _Thickness ("Thickness", Float) = 0.05
    }

    SubShader
    {
        Tags { "RenderType"="Opaque" }
        Cull Front

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
            };

            float _Thickness;
            float4 _Color;

            v2f vert (appdata v)
            {
                v2f o;
                v.vertex.xyz += v.normal * _Thickness;
                o.pos = UnityObjectToClipPos(v.vertex);
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                return _Color;
            }
            ENDCG
        }
    }


}
