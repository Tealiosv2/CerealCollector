using UnityEngine;
using System.Collections;
using TMPro;

public class TextArchitect
{
    private TextMeshProUGUI tmpro_ui;
    private TextMeshPro tmpro_world;
    public TMP_Text tmpro => tmpro_ui != null ? tmpro_ui : tmpro_world;

    public string fullTargetText => preText + targetText;

    public string preText { get; private set; } = "";
    public string targetText { get; private set; } = "";

    private Coroutine buildProcess = null;
    public bool isBuilding => buildProcess != null;

    public enum BuildMethod { instant, typewriter, fade }
    public BuildMethod buildMethod = BuildMethod.typewriter;

    private const float baseSpeed = 0.25f;
    public float speed { get { return baseSpeed * speedMultiplier; } set { speedMultiplier = value; } }
    private float speedMultiplier = 0.25f;

    //public int charactersPerCycle { get { return speed <= 2f ? characterMultiplier : speed <= 2.5f ? characterMultiplier * 2 : characterMultiplier * 3; } }
    public int charactersPerCycle { get {return 1; } }

    private float fadeTime = 5f;
    private float[] randomSpeed = { 0f, 0.10f, 0.35f };


    public TextArchitect(TextMeshProUGUI tmpro_ui)
    {
        this.tmpro_ui = tmpro_ui;
    }

    public TextArchitect(TextMeshPro tmpro_world)
    {
        this.tmpro_world = tmpro_world;
    }


    public Coroutine Build(string text)
    {
        preText = "";
        targetText = text;

        Stop();

        buildProcess = tmpro.StartCoroutine(Building());

        return buildProcess;

    }
    public Coroutine Append(string text)
    {
        preText = tmpro.text;
        targetText = text;

        Stop();

        buildProcess = tmpro.StartCoroutine(Building());
        return buildProcess;

    }
    public void Stop()
    {
        if (!isBuilding)
        {
            return;
        }
        tmpro.StopCoroutine(buildProcess);
        buildProcess = null;

    }
    IEnumerator Building()
    {
        Prepare();

        switch (buildMethod)
        {
            case BuildMethod.typewriter:
                yield return Build_Typewriter();
                break;
            case BuildMethod.fade:
                yield return Build_Fade();

                break;

        }
        OnComplete();
    }
    private void Prepare()
    {
        switch (buildMethod)
        {
            case BuildMethod.instant:
                Prepare_Instant();
                break;
            case BuildMethod.typewriter:
                Prepare_Typewriter();
                break;
            case BuildMethod.fade:
                Prepare_Fade();
                break;
        }
    }

    private void OnComplete()
    {

        buildProcess = null;
    }
    public void ForceComplete()
    {
        switch (buildMethod)
        {
            case BuildMethod.typewriter:
                tmpro.maxVisibleCharacters = tmpro.textInfo.characterCount;
                break;
            case BuildMethod.fade:
                break;
        }
    }
    private void Prepare_Instant()
    {
        tmpro.color = tmpro.color;
        tmpro.text = fullTargetText;
        tmpro.ForceMeshUpdate();
        tmpro.maxVisibleCharacters = tmpro.textInfo.characterCount;
    }
    private void Prepare_Typewriter()
    {
        tmpro.color = tmpro.color;
        tmpro.maxVisibleCharacters = 0;
        tmpro.text = preText;

        if (preText != "")
        {
            tmpro.ForceMeshUpdate();
            tmpro.maxVisibleCharacters = tmpro.textInfo.characterCount;
        }

        tmpro.text += targetText;
        tmpro.ForceMeshUpdate();
    }
    private void Prepare_Fade()
    {

    }
    private IEnumerator Build_Typewriter()
    {
        while (tmpro.maxVisibleCharacters < tmpro.textInfo.characterCount)
        {
            tmpro.maxVisibleCharacters += charactersPerCycle;
            //yield return new WaitForSeconds(0.015f / speed);
            float randomValue = randomSpeed[Random.Range(0, randomSpeed.Length)];
            yield return new WaitForSeconds(randomValue);
        }
        yield return StartFadeOut();


    }

    public IEnumerator StartFadeOut()
    {
        yield return FadeTextOut();
    }
    private IEnumerator FadeTextOut()
    {
                // Get the current color of the text
        Color currentColor = tmpro_ui.color;
        float startAlpha = currentColor.a; // Current alpha value
        float targetAlpha = 0f; // Target alpha for fade-out (fully transparent)
        float elapsedTime = 0f;

        while (elapsedTime < fadeTime)
        {
            // Gradually reduce alpha
            float newAlpha = Mathf.Lerp(startAlpha, targetAlpha, elapsedTime / fadeTime);
            currentColor.a = newAlpha;

            // Apply the updated color
            tmpro_ui.color = currentColor;

            elapsedTime += Time.deltaTime; // Update elapsed time
            yield return null; // Wait until the next frame
        }

        // Ensure the alpha is fully transparent at the end
        currentColor.a = targetAlpha;
        tmpro_ui.color = currentColor;
    
    }
    private IEnumerator Build_Fade()
    {

        yield return null;
    }

}