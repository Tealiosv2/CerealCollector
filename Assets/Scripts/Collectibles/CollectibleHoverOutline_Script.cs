using UnityEngine;

// Draws a white outline around the cereal box (Collectible_Script) under the crosshair.
// Self-installing: no scene setup required.
public class CollectibleHoverOutline_Script : MonoBehaviour
{
    public float maxDistance = 8f;
    public float outlineScale = 0.06f;
    public Color outlineColor = Color.white;

    Material outlineMat;
    GameObject currentOutline;
    Collider currentCollider;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Install()
    {
        if (FindFirstObjectByType<CollectibleHoverOutline_Script>() != null) return;
        var go = new GameObject("CollectibleHoverOutline");
        DontDestroyOnLoad(go);
        go.AddComponent<CollectibleHoverOutline_Script>();
    }

    void Update()
    {
        Collider hovered = FindHovered();
        if (hovered == currentCollider) return;

        if (currentOutline != null) currentOutline.SetActive(false);
        currentCollider = hovered;
        if (hovered == null) { currentOutline = null; return; }

        currentOutline = GetOrCreateOutline(hovered);
        if (currentOutline != null) currentOutline.SetActive(true);
    }

    Collider FindHovered()
    {
        Camera cam = Camera.main;
        if (cam == null) return null;

        // Cursor is locked, so use the screen center. Collectibles use trigger colliders.
        Ray ray = cam.ViewportPointToRay(new Vector3(0.5f, 0.5f, 0f));
        if (Physics.Raycast(ray, out RaycastHit hit, maxDistance, ~0, QueryTriggerInteraction.Collide))
        {
            if (hit.collider.GetComponent<Collectible_Script>() != null)
                return hit.collider;
        }
        return null;
    }

    GameObject GetOrCreateOutline(Collider col)
    {
        var srcFilter = col.GetComponent<MeshFilter>();
        if (srcFilter == null || srcFilter.sharedMesh == null) return null;

        Transform existing = col.transform.Find("HoverOutline");
        if (existing != null) return existing.gameObject;

        if (outlineMat == null)
        {
            Shader sh = Shader.Find("Custom/CerealOutline");
            if (sh == null) { Debug.LogWarning("CerealOutline shader not found"); return null; }
            outlineMat = new Material(sh);
            outlineMat.SetColor("_OutlineColor", outlineColor);
            outlineMat.SetFloat("_OutlineScale", outlineScale);
        }

        var go = new GameObject("HoverOutline");
        go.transform.SetParent(col.transform, false);
        go.AddComponent<MeshFilter>().sharedMesh = srcFilter.sharedMesh;
        var mr = go.AddComponent<MeshRenderer>();
        mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        mr.receiveShadows = false;

        // Scale from the mesh's bounds center, since the pivot may not be centered.
        // A property block avoids creating one Material per collectible.
        mr.sharedMaterial = outlineMat;
        Vector3 c = srcFilter.sharedMesh.bounds.center;
        var block = new MaterialPropertyBlock();
        block.SetVector("_PivotOS", new Vector4(c.x, c.y, c.z, 0));
        mr.SetPropertyBlock(block);
        return go;
    }
}
