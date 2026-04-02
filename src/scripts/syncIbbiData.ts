import axios from "axios";
import { createClient } from "@supabase/supabase-js";
import * as dotenv from "dotenv";

dotenv.config();

const supabaseUrl = process.env.VITE_SUPABASE_URL || "";
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY || "";
const supabase = createClient(supabaseUrl, supabaseKey);

const IBBI_EXPORT_URL = "https://ibbi.gov.in/public-announcement?ann=&title=&date=&export_excel=export_excel";

type IbbiRow = Record<string, string>;

const clean = (value: unknown) => String(value ?? "").replace(/\u00a0/g, " ").trim();

const parseTsv = (content: string): IbbiRow[] => {
  const lines = content
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);

  if (lines.length === 0) return [];

  const headers = lines[0].split("\t").map((header) => clean(header));
  return lines.slice(1).map((line) => {
    const values = line.split("\t");
    return headers.reduce<IbbiRow>((row, header, index) => {
      row[header] = clean(values[index]);
      return row;
    }, {});
  });
};

const inferStatus = (announcementType: string) => {
  const normalized = announcementType.toLowerCase();
  if (normalized.includes("liquidation")) return "Liquidation";
  if (normalized.includes("dissolution")) return "Dissolved";
  return "Under CIRP";
};

async function syncData() {
  console.log("Downloading IBBI TSV export...");

  try {
    const response = await axios.get(IBBI_EXPORT_URL, {
      responseType: "text",
      transformResponse: [(data) => data],
    });

    const rows = parseTsv(response.data as string);
    console.log(`Processing ${rows.length} IBBI rows...`);

    for (const row of rows) {
      const name = row["Name of Corporate Debtor"];
      if (!name) continue;

      const companyData = {
        id: row["CIN No."] || name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
        name,
        cin: row["CIN No."] || "N/A",
        status: inferStatus(row["Announcement Type"]),
        incorporationDate: "N/A",
        registeredAddress: "N/A",
        pan: "N/A",
        type: name.toUpperCase().includes("PRIVATE") ? "Private" : "Public",
        category: row["Announcement Type"] || "N/A",
        origin: "Indian",
        businessAddress: "N/A",
        phone: "N/A",
        email: "N/A",
        website: "N/A",
        listingStatus: "Unlisted",
        lastAGMDate: "N/A",
        lastBSDate: "N/A",
        gstin: "N/A",
        lei: "N/A",
        epfo: "N/A",
        iec: "N/A",
        authCap: 0,
        puc: 0,
        soc: 0,
        revenue: [],
        pat: [],
        netWorth: [],
        promoterHolding: [],
        receivable: "N/A",
        payable: "N/A",
        overview: `Corporate Debtor under IBBI process. Latest announcement: ${row["Date of Announcement"] || "N/A"}`,
        charges: [],
        financials: [],
        ownership: [],
        compliance: [],
        documents: [],
        directors: [],
        news: [],
        trendData: [],
        applicant_name: row["Name of Applicant"] || "N/A",
        ip_name: row["Name of Insolvency Professional"] || "N/A",
        commencement_date: row["Date of Announcement"] || "N/A",
        last_date_claims: row["Last date of Submission"] || "N/A",
      };

      const { error } = await supabase.from("companies").upsert(companyData, { onConflict: "id" });
      if (error) {
        console.error(`Error saving ${name}:`, error.message);
      }
    }

    console.log("Sync complete!");
  } catch (error) {
    console.error("Sync failed:", error);
  }
}

syncData();
