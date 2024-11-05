using System.Collections.Generic;
using System.IO;
using UnityEngine;

public static class FileManager
{
    public static List<string> ReadTextAsset(TextAsset asset, bool includeBlankLines = false)
    {
        List<string> lines = new List<string>();
        using(StringReader sr = new StringReader(asset.text))
        {
            while(sr.Peek() > -1)
            {
                string line = sr.ReadLine();
                if (includeBlankLines || !string.IsNullOrWhiteSpace(line))
                {
                    lines.Add(line);
                }
            }
        }
        return lines;
    }
}