$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root = Join-Path $PSScriptRoot 'resume-test-docx'
if (Test-Path $root) {
  Remove-Item $root -Recurse -Force
}
New-Item -ItemType Directory -Path $root | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root '_rels') | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root 'word') | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root 'word\_rels') | Out-Null
@'
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'@ | Out-File -Encoding ascii (Join-Path $root '[Content_Types].xml')
@'
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'@ | Out-File -Encoding ascii (Join-Path $root '_rels\.rels')
@'
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Test User Beta</w:t></w:r></w:p>
    <w:p><w:r><w:t>test.user.beta+20260403@example.com</w:t></w:r></w:p>
    <w:p><w:r><w:t>Senior Software Engineer</w:t></w:r></w:p>
    <w:p><w:r><w:t>Skills: Python, FastAPI, PostgreSQL, Docker, Vue, Playwright</w:t></w:r></w:p>
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>
  </w:body>
</w:document>
'@ | Out-File -Encoding ascii (Join-Path $root 'word\document.xml')
$zip = Join-Path $PSScriptRoot 'resume-test.docx'
if (Test-Path $zip) {
  Remove-Item $zip -Force
}
[System.IO.Compression.ZipFile]::CreateFromDirectory($root, $zip)
Write-Host $zip
