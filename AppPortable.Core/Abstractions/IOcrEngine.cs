namespace AppPortable.Core.Abstractions;

public interface IOcrEngine
{
    bool IsAvailable { get; }
    Task<IReadOnlyDictionary<int, (string Text, double? Confidence)>> ExtractByPageAsync(string pdfPath, CancellationToken cancellationToken = default);
}
