using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Win32;
using AppPortable.Core.Services;
using AppPortable.Core.Models;
using AppPortable.Infrastructure.Persistence;

namespace AppPortable.Desktop.ViewModels;

public partial class MainWindowViewModel(DocumentPipelineService pipeline, AppPaths paths) : ObservableObject
{
    public ObservableCollection<DocumentRecord> Documents { get; } = [];
    public ObservableCollection<SearchResultRecord> Results { get; } = [];

    [ObservableProperty] private DocumentRecord? selectedDocument;
    [ObservableProperty] private SearchResultRecord? selectedResult;
    [ObservableProperty] private string queryText = string.Empty;
    [ObservableProperty] private string statusText = "Listo";
    [ObservableProperty] private string lastLog = "Sin actividad";
    [ObservableProperty] private int progressValue;
    [ObservableProperty] private string detailText = "Sin selección";
    [ObservableProperty] private string? selectedPdfPath;

    partial void OnSelectedDocumentChanged(DocumentRecord? value)
    {
        if (value is null) return;
        DetailText = $"Documento: {value.SourceFile}\nID: {value.DocumentId}\nPáginas: {value.TotalPages}\nChunks: {value.Chunks.Count}\nWarnings: {string.Join(", ", value.Warnings)}";
    }

    partial void OnSelectedResultChanged(SearchResultRecord? value)
    {
        if (value is null) return;
        DetailText = $"Documento: {value.SourceFile}\nChunk: {value.ChunkId}\nPáginas: {value.PageStart}-{value.PageEnd}\nScore: {value.Score}\n\n{value.Snippet}";
    }

    [RelayCommand]
    private void PickDocument()
    {
        var dialog = new OpenFileDialog
        {
            Filter = "PDF (*.pdf)|*.pdf",
            Multiselect = false,
            InitialDirectory = paths.Input
        };
        if (dialog.ShowDialog() == true)
        {
            SelectedPdfPath = dialog.FileName;
            StatusText = $"Listo para procesar: {Path.GetFileName(SelectedPdfPath)}";
        }
    }

    [RelayCommand]
    private async Task ProcessSelected()
    {
        if (string.IsNullOrWhiteSpace(SelectedPdfPath) || !File.Exists(SelectedPdfPath))
        {
            StatusText = "Seleccione un PDF válido";
            return;
        }

        try
        {
            ProgressValue = 10;
            StatusText = "Extrayendo texto y OCR...";
            var doc = await pipeline.ProcessAsync(SelectedPdfPath, new ProcessingOptions());
            ProgressValue = 90;
            Documents.Insert(0, doc);
            SelectedDocument = doc;
            LastLog = $"Procesado: {doc.DocumentId} | chunks: {doc.Chunks.Count}";
            StatusText = "Procesamiento finalizado";
            ProgressValue = 100;
        }
        catch (Exception ex)
        {
            StatusText = "Error en procesamiento";
            LastLog = ex.Message;
            ProgressValue = 0;
        }
    }

    [RelayCommand]
    private async Task Search()
    {
        Results.Clear();
        var results = await pipeline.SearchAsync(QueryText, 30);
        foreach (var result in results)
        {
            Results.Add(result);
        }

        StatusText = $"Resultados: {results.Count}";
        LastLog = results.Count == 0 ? "Sin coincidencias" : "Búsqueda completada";
    }
}
