namespace AppPortable.Core.Models;

public sealed class ExtractionSummary
{
    public bool OcrEnabled { get; set; }
    public bool OcrAvailable { get; set; }
    public bool OcrUsed { get; set; }
    public int OcrPages { get; set; }
    public int NativePages { get; set; }
    public bool HasExtractableText { get; set; }
}
