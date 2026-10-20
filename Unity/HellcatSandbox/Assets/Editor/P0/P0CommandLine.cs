using System;

namespace Hellcat.EditorTools.P0
{
    /// <summary>Reads "-name value" pairs from the editor command line.</summary>
    public static class P0CommandLine
    {
        public static string GetValue(string name, string fallback)
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
            }
            return fallback;
        }
    }
}
