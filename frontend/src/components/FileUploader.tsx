"use client";

import { useCallback, useEffect, useState } from "react";
import { Upload, X, FileText, FileSpreadsheet, File, Image } from "lucide-react";
import { uploadFile, deleteUpload, UploadResponse } from "@/lib/api";

interface FileUploaderProps {
  files: UploadResponse[];
  onFilesChange: (files: UploadResponse[]) => void;
}

function getFileIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "csv") return FileSpreadsheet;
  if (ext === "pdf" || ext === "txt" || ext === "md") return FileText;
  if (ext === "png" || ext === "jpg" || ext === "jpeg" || ext === "gif" || ext === "webp") return Image;
  return File;
}

export default function FileUploader({ files, onFilesChange }: FileUploaderProps) {
  const [uploads, setUploads] = useState<UploadResponse[]>(files);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync internal state when parent resets files (e.g. after send)
  useEffect(() => {
    setUploads(files);
  }, [files]);

  const handleUpload = useCallback(
    async (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      setUploading(true);
      setError(null);

      try {
        const results: UploadResponse[] = [];
        for (const file of Array.from(fileList)) {
          const res = await uploadFile(file);
          results.push(res);
        }
        const updated = [...uploads, ...results];
        setUploads(updated);
        onFilesChange(updated);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [uploads, onFilesChange]
  );

  const removeFile = useCallback(
    (uploadId: string) => {
      const updated = uploads.filter((u) => u.upload_id !== uploadId);
      setUploads(updated);
      onFilesChange(updated);
      // Delete from server storage (fire-and-forget)
      deleteUpload(uploadId).catch(() => {});
    },
    [uploads, onFilesChange]
  );

  return (
    <div>
      {/* Drop zone / upload button */}
      <label
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed cursor-pointer transition-all ${
          uploading
            ? "border-white/20 bg-white/[0.03]"
            : "border-white/[0.08] hover:border-white/20 hover:bg-white/[0.02]"
        }`}
      >
        <Upload className="w-4 h-4 text-muted" />
        <span className="text-sm text-muted">
          {uploading ? "Uploading..." : "Attach files (CSV, PDF, TXT, PNG, JPG...)"}
        </span>
        <input
          type="file"
          className="hidden"
          multiple
          accept=".csv,.txt,.md,.json,.pdf,.py,.js,.ts,.yaml,.yml,.log,.png,.jpg,.jpeg,.gif,.webp"
          onChange={(e) => handleUpload(e.target.files)}
          disabled={uploading}
        />
      </label>

      {/* Error */}
      {error && (
        <p className="mt-1 text-xs text-error">{error}</p>
      )}

      {/* Uploaded file chips */}
      {uploads.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {uploads.map((u) => {
            const Icon = getFileIcon(u.filename);
            return (
              <div
                key={u.upload_id}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/[0.06] text-xs"
              >
                <Icon className="w-3.5 h-3.5 text-white/50" />
                <span className="text-foreground max-w-[120px] truncate">
                  {u.filename}
                </span>
                <span className="text-muted">
                  ({(u.size / 1024).toFixed(1)}KB)
                </span>
                <button
                  onClick={() => removeFile(u.upload_id)}
                  className="ml-1 text-muted hover:text-error transition-colors cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
