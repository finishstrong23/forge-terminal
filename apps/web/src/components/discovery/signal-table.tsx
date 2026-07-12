"use client";

import React from "react";
import Link from "next/link";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import {
  ArrowUpDown,
  Shield,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatUsd, scoreColor, scoreBg } from "@/lib/utils";

export interface TokenSignal {
  id: string;
  symbol: string;
  name: string;
  image_uri: string | null;
  token_address: string;
  price_usd: number;
  market_cap: number;
  volume_1h: number;
  liquidity_usd: number;
  rug_risk_score: number;
  momentum_score: number;
  confidence_score: number;
  age_minutes: number;
  holder_count: number;
  buy_ratio_1h: number;
  is_honeypot: boolean;
  flags: string[];
}

function ScoreCell({ score, inverted = false }: { score: number; inverted?: boolean }) {
  return (
    <div
      className={cn(
        "inline-flex items-center justify-center rounded border px-2 py-0.5 font-mono-numbers text-xs font-bold",
        scoreBg(score, inverted)
      )}
    >
      <span className={scoreColor(score, inverted)}>{score}</span>
    </div>
  );
}

function AgeCell({ minutes }: { minutes: number }) {
  let display: string;
  if (minutes < 60) display = `${Math.round(minutes)}m`;
  else if (minutes < 1440) display = `${(minutes / 60).toFixed(1)}h`;
  else display = `${(minutes / 1440).toFixed(1)}d`;

  return <span className="font-mono-numbers text-xs">{display}</span>;
}

const columns: ColumnDef<TokenSignal>[] = [
  {
    accessorKey: "symbol",
    header: "Token",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        {/* Token logos live on arbitrary hosts (IPFS gateways etc.), so a
            plain img with a hide-on-error fallback beats next/image here. */}
        {row.original.image_uri && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={row.original.image_uri}
            alt=""
            className="h-6 w-6 shrink-0 rounded-full bg-surface object-cover"
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        )}
        <div className="flex flex-col">
          <span className="font-medium text-foreground">{row.original.symbol}</span>
          <span className="text-xs text-muted-foreground truncate max-w-[120px]">
            {row.original.name}
          </span>
        </div>
      </div>
    ),
    size: 140,
  },
  {
    accessorKey: "age_minutes",
    header: "Age",
    cell: ({ getValue }) => <AgeCell minutes={getValue<number>()} />,
    size: 70,
  },
  {
    accessorKey: "market_cap",
    header: ({ column }) => (
      <button
        className="flex items-center gap-1"
        onClick={() => column.toggleSorting()}
      >
        MCap
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs">{formatUsd(getValue<number>())}</span>
    ),
    size: 90,
  },
  {
    accessorKey: "volume_1h",
    header: ({ column }) => (
      <button
        className="flex items-center gap-1"
        onClick={() => column.toggleSorting()}
      >
        Vol 1h
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs">{formatUsd(getValue<number>())}</span>
    ),
    size: 90,
  },
  {
    accessorKey: "rug_risk_score",
    header: ({ column }) => (
      <button
        className="flex items-center gap-1"
        onClick={() => column.toggleSorting()}
      >
        <Shield className="h-3 w-3" />
        Risk
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ getValue }) => <ScoreCell score={getValue<number>()} inverted />,
    size: 80,
  },
  {
    accessorKey: "momentum_score",
    header: ({ column }) => (
      <button
        className="flex items-center gap-1"
        onClick={() => column.toggleSorting()}
      >
        <TrendingUp className="h-3 w-3" />
        Momentum
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ getValue }) => <ScoreCell score={getValue<number>()} />,
    size: 100,
  },
  {
    accessorKey: "holder_count",
    header: "Holders",
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs">{getValue<number>()}</span>
    ),
    size: 70,
  },
  {
    accessorKey: "buy_ratio_1h",
    header: "Buy %",
    cell: ({ getValue }) => {
      const ratio = getValue<number>();
      return (
        <span
          className={cn(
            "font-mono-numbers text-xs",
            ratio >= 60 ? "text-green-400" : ratio >= 40 ? "text-foreground" : "text-red-400"
          )}
        >
          {ratio.toFixed(0)}%
        </span>
      );
    },
    size: 70,
  },
  {
    id: "flags",
    header: "",
    cell: ({ row }) => (
      <div className="flex items-center gap-1">
        {row.original.is_honeypot && (
          <Badge variant="danger" className="text-[10px]">
            <AlertTriangle className="mr-0.5 h-2.5 w-2.5" />
            HONEYPOT
          </Badge>
        )}
      </div>
    ),
    size: 100,
  },
  {
    id: "actions",
    header: "",
    cell: ({ row }) => (
      <div className="flex items-center gap-1">
        {/* stopPropagation: the row click opens the detail panel. */}
        <Button variant="default" size="sm" className="h-7 text-xs" asChild>
          <Link
            href={`/execute?mint=${encodeURIComponent(row.original.token_address)}`}
            onClick={(e) => e.stopPropagation()}
          >
            Buy
          </Link>
        </Button>
      </div>
    ),
    size: 70,
  },
];

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 12 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-md" />
      ))}
    </div>
  );
}

interface SignalTableProps {
  data: TokenSignal[];
  loading?: boolean;
  onRowClick?: (signal: TokenSignal) => void;
}

export function SignalTable({ data, loading, onRowClick }: SignalTableProps) {
  const [sorting, setSorting] = React.useState<SortingState>([
    { id: "momentum_score", desc: true },
  ]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  if (loading) return <TableSkeleton />;

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr
              key={headerGroup.id}
              className="border-b border-border bg-surface"
            >
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-3 py-2 text-left text-xs font-medium text-muted-foreground"
                  style={{ width: header.getSize() }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="py-12 text-center text-sm text-muted-foreground"
              >
                No tokens match your filters. Try adjusting the criteria.
              </td>
            </tr>
          ) : (
            table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={() => onRowClick?.(row.original)}
                className="cursor-pointer border-b border-border-muted transition-colors hover:bg-surface-hover"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
