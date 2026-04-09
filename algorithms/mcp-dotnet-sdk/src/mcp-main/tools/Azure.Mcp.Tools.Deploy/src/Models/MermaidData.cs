// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

using System.Text.Json.Serialization;

namespace Azure.Mcp.Tools.Deploy.Models;

public sealed class MermaidData
{
    [JsonPropertyName("code")]
    public string Code { get; set; } = string.Empty;

    [JsonPropertyName("mermaid")]
    public MermaidConfig Mermaid { get; set; } = new();
}

public sealed class MermaidConfig
{
    [JsonPropertyName("theme")]
    public string Theme { get; set; } = "default";
}
