namespace AppPortable.Domain.Models;

public sealed class PageContent
{
    public int PageNumber { get; set; }
    public ExtractionLayer ExtractionLayer { get; set; }
    public double? OcrConfidence { get; set; }
    public string Text { get; set; } = string.Empty;
    public int TextLength => Text.Length;
    public List<string> Warnings { get; set; } = [];
}
