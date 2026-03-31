namespace AppPortable.Infrastructure.Persistence;

public sealed class AppPaths
{
    public string Root { get; }
    public string Input { get; }
    public string Output { get; }
    public string Documents { get; }
    public string Json { get; }
    public string Chunks { get; }
    public string Index { get; }
    public string Temp { get; }
    public string Logs { get; }

    public AppPaths(string? root = null)
    {
        Root = root ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AppPortable");
        Input = Path.Combine(Root, "input");
        Output = Path.Combine(Root, "output");
        Documents = Path.Combine(Output, "documents");
        Json = Path.Combine(Output, "json");
        Chunks = Path.Combine(Output, "chunks");
        Index = Path.Combine(Output, "index");
        Temp = Path.Combine(Root, "temp");
        Logs = Path.Combine(Root, "logs");
    }

    public void EnsureAll()
    {
        foreach (var path in new[] { Root, Input, Output, Documents, Json, Chunks, Index, Temp, Logs })
        {
            Directory.CreateDirectory(path);
        }
    }
}
