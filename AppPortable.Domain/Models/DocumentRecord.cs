namespace AppPortable.Domain.Models;

public sealed class DocumentRecord
{
    public string DocumentId { get; set; } = string.Empty;
    public string SourceFile { get; set; } = string.Empty;
    public string SourcePath { get; set; } = string.Empty;
    public DateTime ProcessedAtUtc { get; set; }
    public int TotalPages { get; set; }
    public ExtractionSummary ExtractionSummary { get; set; } = new();
    public List<PageContent> Pages { get; set; } = [];
    public List<ChunkRecord> Chunks { get; set; } = [];
    public List<string> Warnings { get; set; } = [];
    public string CleanFullText => string.Join("\n\n", Pages.Where(p => !string.IsNullOrWhiteSpace(p.Text)).Select(p => p.Text));
}
