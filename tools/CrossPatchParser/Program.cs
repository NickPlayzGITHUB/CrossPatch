using System.CommandLine;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Versions;
using System.Text.Json;

namespace CrossPatchParser;

class Program
{
    static async Task<int> Main(string[] args)
    {
        var nameOption = new Option<string>("--mod-name", "Mod name");
        var authorOption = new Option<string>("--mod-author", "Mod author");
        var versionOption = new Option<string>("--mod-version", "Mod version");
        var pathOption = new Option<DirectoryInfo>("--path", "Mod path containing pak, ucas, and utoc") { IsRequired = true };
        var outputOption = new Option<FileInfo?>("--output", "Output file path (defaults to stdout)");
        var mountPointOption = new Option<string>("--mount-point", "Mount point for pak files");

        var rootCommand = new RootCommand("CrossPatch Mod Parser - Analyzes UE4/5 pak files and generates mod info")
        {
            nameOption,
            authorOption,
            versionOption,
            pathOption,
            outputOption,
            mountPointOption
        };

        rootCommand.SetHandler(async (path, name, author, version, output, mountPoint) =>
        {
            try 
            {
                // Create provider configured for UE5; search subdirectories
                var provider = new DefaultFileProvider(path.FullName, SearchOption.AllDirectories, false, new VersionContainer(EGame.GAME_UE5_4));

                Console.Error.WriteLine($"Initializing provider for path: {path.FullName}");
                provider.Initialize();

                // Submit a blank encryption key - most mods aren't encrypted
                provider.SubmitKey(new FGuid(), new FAesKey(new byte[32]));

                // Get all pak, utoc, and ucas files
                var pakFiles = Directory.GetFiles(path.FullName, "*.pak", SearchOption.AllDirectories);
                var utocFiles = Directory.GetFiles(path.FullName, "*.utoc", SearchOption.AllDirectories);
                var ucasFiles = Directory.GetFiles(path.FullName, "*.ucas", SearchOption.AllDirectories);

                Console.Error.WriteLine($"Found: {pakFiles.Length} pak files, {utocFiles.Length} utoc files, {ucasFiles.Length} ucas files");

                var pakInfo = new List<object>();

                // Build a global index of all files discovered by the provider and extract common metadata via reflection
                var filesIndex = new List<object>();
                foreach (var kv in provider.Files)
                {
                    try
                    {
                        var fileKey = kv.Key.ToString();
                        var fileVal = kv.Value;
                        var valType = fileVal.GetType();

                        object size = null;
                        object compressedSize = null;
                        object offset = null;
                        object archiveName = null;

                        var prop = valType.GetProperty("Size");
                        if (prop != null) size = prop.GetValue(fileVal);
                        prop = valType.GetProperty("CompressedSize");
                        if (prop != null) compressedSize = prop.GetValue(fileVal);
                        prop = valType.GetProperty("Offset");
                        if (prop != null) offset = prop.GetValue(fileVal);
                        prop = valType.GetProperty("ArchiveName");
                        if (prop != null) archiveName = prop.GetValue(fileVal)?.ToString();

                        filesIndex.Add(new {
                            path = fileKey,
                            size = size,
                            compressed_size = compressedSize,
                            offset = offset,
                            archive = archiveName
                        });
                    }
                    catch (Exception)
                    {
                        // ignore reflection failures per-entry
                    }
                }

                // Map to track which IoStore files we've processed
                var processedIoStores = new HashSet<string>();

                // Process pak files
                foreach (var pakFile in pakFiles)
                {
                    Console.Error.WriteLine($"Processing pak file: {pakFile}");
                    try
                    {
                        pakInfo.Add(new
                        {
                            file_name = Path.GetFileName(pakFile),
                            file_path = Path.GetRelativePath(path.FullName, pakFile),
                            file_count = provider.Files.Count,
                            total_size = provider.Files.Values.Sum(f => f.Size),
                            mount_point = mountPoint ?? "",
                            files = provider.Files.Keys.Select(k => k.ToString()).ToList()
                        });
                    }
                    catch (Exception ex)
                    {
                        Console.Error.WriteLine($"Warning: Error processing {pakFile}: {ex.Message}");
                    }
                }

                // Process IoStore files (utoc/ucas pairs)
                foreach (var utocFile in utocFiles)
                {
                    var baseName = Path.GetFileNameWithoutExtension(utocFile);
                    if (processedIoStores.Contains(baseName))
                        continue;

                    var ucasFile = ucasFiles.FirstOrDefault(f => 
                        Path.GetFileNameWithoutExtension(f) == baseName);

                    if (ucasFile != null)
                    {
                        Console.Error.WriteLine($"Processing IoStore: {baseName}");
                        try
                        {
                            pakInfo.Add(new
                            {
                                file_name = $"{baseName} (IoStore)",
                                utoc_path = Path.GetRelativePath(path.FullName, utocFile),
                                ucas_path = Path.GetRelativePath(path.FullName, ucasFile),
                                file_count = provider.Files.Count,
                                total_size = provider.Files.Values.Sum(f => f.Size),
                                mount_point = mountPoint ?? "",
                              files = provider.Files.Keys.Select(k => k.ToString()).ToList()
                            });
                            processedIoStores.Add(baseName);
                        }
                        catch (Exception ex)
                        {
                            Console.Error.WriteLine($"Warning: Error processing IoStore {baseName}: {ex.Message}");
                        }
                    }
                }

                // Compute totals using long to avoid implicit conversion issues
                var totalFiles = pakInfo.Select(p => (long)((dynamic)p).file_count).Sum();
                var totalSize = pakInfo.Select(p => (long)((dynamic)p).total_size).Sum();

                var info = new
                {
                    name = name ?? "YOUR MOD NAME",
                    version = version ?? "1.0",
                    author = author ?? "Unknown",
                    mod_type = "pak",
                    pak_data = new
                    {
                        pak_files = pakInfo,
                        files_index = filesIndex,
                        total_files = totalFiles,
                        total_size = totalSize
                    }
                };

                var json = JsonSerializer.Serialize(info, new JsonSerializerOptions 
                { 
                    WriteIndented = true 
                });

                if (output != null)
                {
                    await File.WriteAllTextAsync(output.FullName, json);
                }
                else
                {
                    Console.WriteLine(json);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Error: {ex.Message}");
                Environment.Exit(1);
            }
        },
        pathOption, nameOption, authorOption, versionOption, outputOption, mountPointOption);

        return await rootCommand.InvokeAsync(args);
    }
}