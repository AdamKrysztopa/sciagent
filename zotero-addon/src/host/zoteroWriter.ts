/**
 * ZAP-6/7/8: Native Zotero write path.
 *
 * - ZAP-6: resolveOrCreateCollection — finds or creates a Zotero collection by name.
 * - ZAP-7: createItemsNative — idempotent item creation with DOI / title-hash dedup.
 * - ZAP-8: attachPdf — downloads and attaches a PDF via Zotero.Attachments.importFromURL.
 */

import type { NormalizedPaper } from "../shared/contracts";
import type {
  ZoteroAttachments,
  ZoteroCollection,
  ZoteroCollections,
  ZoteroGlobal,
  ZoteroItem,
  ZoteroItems,
  ZoteroLibraries,
} from "./zoteroTypes";

export interface NativeItemResult {
  paper: NormalizedPaper;
  status: "created" | "unchanged" | "failed";
  itemKey: string | null;
  reason: string | null;
  /** null when PDF import was disabled or item was not created; "skipped" when no pdf_url. */
  pdfStatus: "attached" | "failed" | "skipped" | null;
}

export interface NativeWriteResult {
  collectionKey: string;
  collectionName: string;
  created: number;
  unchanged: number;
  failed: number;
  outcomes: NativeItemResult[];
  pdfAttached: number;
  pdfFailed: number;
}

// Services injected so that callers can swap them in tests.
export interface ZoteroWriterServices {
  collections: ZoteroCollections;
  items: ZoteroItems;
  attachments: ZoteroAttachments;
  libraries: ZoteroLibraries;
}

function servicesFromZotero(z: ZoteroGlobal): ZoteroWriterServices {
  return {
    collections: z.Collections,
    items: z.Items,
    attachments: z.Attachments,
    libraries: z.Libraries,
  };
}

// Stable hash of title + first-author for dedup when DOI is absent.
function titleAuthorHash(title: string, authors: string[]): string {
  const key = `${title.toLowerCase().trim()}|${(authors[0] ?? "").toLowerCase().trim()}`;
  // Simple deterministic hash — not cryptographic.
  let h = 0;
  for (let i = 0; i < key.length; i++) {
    h = Math.imul(31, h) + key.charCodeAt(i);
    h |= 0;
  }
  return `ta-${(h >>> 0).toString(16)}`;
}

// --- ZAP-6: Collection resolver ---

/**
 * Resolves or creates a top-level collection in the user library.
 * Returns the numeric collection ID.
 */
async function resolveOrCreateCollection(
  name: string,
  services: ZoteroWriterServices,
): Promise<{ id: number; key: string }> {
  const libraryID = services.libraries.getUserLibrary().libraryID;
  const existing = services.collections
    .getByLibrary(libraryID)
    .find((c: ZoteroCollection) => c.name === name && c.parentKey === false);

  if (existing !== undefined) {
    return { id: existing.id, key: existing.key };
  }

  const created = await services.collections.add({ name });
  return { id: created.id, key: created.key };
}

// --- ZAP-7: Idempotent item creation ---

/**
 * Creates items in Zotero from normalized papers.
 * Skips duplicates identified by DOI or title+first-author hash.
 */
async function createItemsNative(
  papers: NormalizedPaper[],
  collectionId: number,
  services: ZoteroWriterServices,
): Promise<NativeItemResult[]> {
  const libraryID = services.libraries.getUserLibrary().libraryID;
  // Build dedup indexes from existing items.
  const existingItems = services.items.getAll(libraryID);
  const doiIndex = new Map<string, ZoteroItem>();
  const hashIndex = new Map<string, ZoteroItem>();

  for (const item of existingItems) {
    const doi = String(item.getField("DOI") ?? "").trim().toLowerCase();
    if (doi) doiIndex.set(doi, item);
    const title = String(item.getField("title") ?? "").trim();
    const creators = String(item.getField("firstCreator") ?? "").trim();
    if (title) {
      const h = titleAuthorHash(title, [creators]);
      hashIndex.set(h, item);
    }
  }

  const outcomes: NativeItemResult[] = [];

  for (const paper of papers) {
    // Check DOI dedup first, then title-author hash.
    const doi = (paper.doi ?? "").trim().toLowerCase();
    const hash = titleAuthorHash(paper.title, paper.authors);

    const dupItem = (doi !== "" ? doiIndex.get(doi) : undefined) ?? hashIndex.get(hash);
    if (dupItem !== undefined) {
      outcomes.push({
        paper,
        status: "unchanged",
        itemKey: dupItem.key,
        reason: doi && doiIndex.has(doi) ? "doi_match" : "title_author_hash_match",
        pdfStatus: null,
      });
      continue;
    }

    try {
      const item = await services.items.add(
        {
          itemType: "journalArticle",
          title: paper.title,
          DOI: paper.doi ?? "",
          abstractNote: paper.abstract ?? "",
          year: paper.year ?? "",
          url: paper.url ?? "",
        },
        libraryID,
      );
      item.addToCollection(collectionId);
      await item.save();
      outcomes.push({ paper, status: "created", itemKey: item.key, reason: null, pdfStatus: null });
    } catch (err: unknown) {
      outcomes.push({
        paper,
        status: "failed",
        itemKey: null,
        reason: err instanceof Error ? err.message : String(err),
        pdfStatus: null,
      });
    }
  }

  return outcomes;
}

// --- ZAP-8: PDF attachment ---

/**
 * Attaches a PDF to an existing Zotero item by URL.
 * Returns true on success, false on failure.
 */
async function attachPdf(
  itemId: number,
  pdfUrl: string,
  title: string,
  services: ZoteroWriterServices,
): Promise<boolean> {
  try {
    const result = await services.attachments.importFromURL({
      url: pdfUrl,
      parentItemID: itemId,
      title: `${title} (PDF)`,
      contentType: "application/pdf",
    });
    return result !== false;
  } catch {
    return false;
  }
}

// --- Orchestrator ---

/**
 * Full native write flow: resolve/create collection → create items → attach PDFs.
 */
export async function nativeWrite(
  papers: NormalizedPaper[],
  collectionName: string,
  enablePdfImport: boolean,
  zotero: ZoteroGlobal,
): Promise<NativeWriteResult> {
  const services = servicesFromZotero(zotero);
  const collection = await resolveOrCreateCollection(collectionName, services);
  const rawOutcomes = await createItemsNative(papers, collection.id, services);

  let pdfAttached = 0;
  let pdfFailed = 0;
  // Map from itemKey → per-item PDF outcome (only for newly created items).
  const pdfStatusByKey = new Map<string, "attached" | "failed" | "skipped">();

  if (enablePdfImport) {
    // Resolve library items once so we can look up numeric IDs by key.
    const libraryID = services.libraries.getUserLibrary().libraryID;
    const allItems = services.items.getAll(libraryID);

    for (const outcome of rawOutcomes) {
      if (outcome.status !== "created" || outcome.itemKey === null) continue;
      const pdfUrl = outcome.paper.pdf_url;
      if (!pdfUrl) {
        pdfStatusByKey.set(outcome.itemKey, "skipped");
        continue;
      }

      const item = allItems.find((it: ZoteroItem) => it.key === outcome.itemKey);
      if (!item) {
        pdfStatusByKey.set(outcome.itemKey, "failed");
        pdfFailed++;
        continue;
      }

      const ok = await attachPdf(item.id, pdfUrl, outcome.paper.title, services);
      pdfStatusByKey.set(outcome.itemKey, ok ? "attached" : "failed");
      if (ok) {
        pdfAttached++;
      } else {
        pdfFailed++;
      }
    }
  }

  // Rebuild outcomes with resolved pdfStatus.
  const outcomes: NativeItemResult[] = rawOutcomes.map((o) => ({
    ...o,
    pdfStatus: o.itemKey !== null ? (pdfStatusByKey.get(o.itemKey) ?? null) : null,
  }));

  return {
    collectionKey: collection.key,
    collectionName,
    created: outcomes.filter((o) => o.status === "created").length,
    unchanged: outcomes.filter((o) => o.status === "unchanged").length,
    failed: outcomes.filter((o) => o.status === "failed").length,
    outcomes,
    pdfAttached,
    pdfFailed,
  };
}
