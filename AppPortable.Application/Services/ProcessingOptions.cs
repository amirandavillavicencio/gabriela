namespace AppPortable.Application.Services;

public sealed class ProcessingOptions
{
    public bool ForceOcr { get; set; }
    public int MinChunkChars { get; set; } = 500;
    public int MaxChunkChars { get; set; } = 1000;
    public int OverlapChars { get; set; } = 120;
}
