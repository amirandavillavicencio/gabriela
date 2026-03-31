using System.Text.RegularExpressions;
using AppPortable.Core.Abstractions;
using AppPortable.Core.Models;

namespace AppPortable.Infrastructure.Processing;

public sealed class SemanticChunker : IChunker
{
    public IReadOnlyList<ChunkRecord> CreateChunks(DocumentRecord document, int minChars = 500, int maxChars = 1000, int overlapChars = 120)
    {
        var units = new List<(int page, string text, ExtractionLayer layer, double? confidence)>();
        foreach (var page in document.Pages)
        {
            if (string.IsNullOrWhiteSpace(page.Text)) continue;
            foreach (var paragraph in SplitParagraphs(page.Text))
            {
                foreach (var part in SplitByLength(paragraph, maxChars))
                {
                    units.Add((page.PageNumber, part.Trim(), page.ExtractionLayer, page.OcrConfidence));
                }
            }
        }

        var result = new List<ChunkRecord>();
        var buffer = new List<(int page, string text, ExtractionLayer layer, double? confidence)>();

        void Flush()
        {
            if (buffer.Count == 0) return;
            var text = string.Join("\n\n", buffer.Select(b => b.text)).Trim();
            if (text.Length < minChars && result.Count > 0) return;
            var pages = buffer.Select(b => b.page).ToList();
            var confidences = buffer.Where(b => b.confidence.HasValue).Select(b => b.confidence!.Value).ToList();
            var chunkIndex = result.Count + 1;
            result.Add(new ChunkRecord
            {
                ChunkId = $"{document.DocumentId}_chunk_{chunkIndex:0000}",
                DocumentId = document.DocumentId,
                SourceFile = document.SourceFile,
                PageStart = pages.Min(),
                PageEnd = pages.Max(),
                ChunkIndex = chunkIndex,
                Text = text,
                ExtractionLayersInvolved = buffer.Select(b => b.layer.ToString().ToLowerInvariant()).Distinct().OrderBy(s => s).ToList(),
                AvgConfidence = confidences.Count == 0 ? null : Math.Round(confidences.Average(), 4),
                Metadata = new Dictionary<string, string> { ["unit_count"] = buffer.Count.ToString() }
            });

            var overlap = text.Length <= overlapChars ? text : text[^overlapChars..];
            var tail = buffer.Last();
            buffer = string.IsNullOrWhiteSpace(overlap) ? [] : [(tail.page, overlap, tail.layer, tail.confidence)];
        }

        foreach (var unit in units)
        {
            var current = string.Join("\n\n", buffer.Select(b => b.text));
            var candidate = string.IsNullOrWhiteSpace(current) ? unit.text : current + "\n\n" + unit.text;
            if (current.Length >= minChars && candidate.Length > maxChars)
            {
                Flush();
            }
            buffer.Add(unit);
            if (string.Join("\n\n", buffer.Select(b => b.text)).Length >= maxChars)
            {
                Flush();
            }
        }

        Flush();
        return result;
    }

    private static IEnumerable<string> SplitParagraphs(string text) => Regex.Split(text, "\\n\\s*\\n").Where(x => !string.IsNullOrWhiteSpace(x));

    private static IEnumerable<string> SplitByLength(string text, int maxChars)
    {
        if (text.Length <= maxChars) return [text];
        var sentences = Regex.Split(text, @"(?<=[\.!?;:])\s+").Where(x => !string.IsNullOrWhiteSpace(x));
        var chunks = new List<string>();
        var current = "";
        foreach (var sentence in sentences)
        {
            var candidate = string.IsNullOrWhiteSpace(current) ? sentence : $"{current} {sentence}";
            if (candidate.Length <= maxChars)
            {
                current = candidate;
                continue;
            }
            if (!string.IsNullOrWhiteSpace(current)) chunks.Add(current);
            current = sentence;
        }
        if (!string.IsNullOrWhiteSpace(current)) chunks.Add(current);
        return chunks;
    }
}
