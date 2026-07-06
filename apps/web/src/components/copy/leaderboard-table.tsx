"use client";

import React from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, Link2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, truncateAddress, scoreColor, scoreBg } from "@/lib/utils";
import {
  formatRelativeTime,
  formatSol,
  type WalletRow,
} from "@/lib/copy-leaderboard";

function GradeCell({ score, grade }: { score: number; grade: string }) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono-numbers text-xs font-bold",
        scoreBg(score)
      )}
    >
      <span className={scoreColor(score)}>{grade}</span>
      <span className="text-[10px] font-normal text-muted-foreground">
        {score.toFixed(0)}
      </span>
    </div>
  );
}

const columns: ColumnDef<WalletRow>[] = [
  {
    accessorKey: "rank",
    header: "#",
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs text-muted-foreground">
        {getValue<number>()}
      </span>
    ),
    size: 40,
  },
  {
    accessorKey: "wallet_address",
    header: "Wallet",
    cell: ({ row }) => (
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-xs text-foreground">
          {truncateAddress(row.original.wallet_address, 5)}
        </span>
        {row.original.is_clustered && (
          <Badge variant="warning" className="text-[10px]" title="Linked to a funding cluster">
            <Link2 className="mr-0.5 h-2.5 w-2.5" />
            CLUSTER
          </Badge>
        )}
      </div>
    ),
    size: 170,
  },
  {
    accessorKey: "net_sol",
    header: ({ column }) => (
      <button className="flex items-center gap-1" onClick={() => column.toggleSorting()}>
        Net SOL
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ getValue }) => {
      const v = getValue<number>();
      return (
        <span
          className={cn(
            "font-mono-numbers text-xs",
            v > 0 ? "text-green-400" : v < 0 ? "text-red-400" : "text-foreground"
          )}
        >
          {formatSol(v)}
        </span>
      );
    },
    size: 100,
  },
  {
    accessorKey: "win_rate",
    header: ({ column }) => (
      <button className="flex items-center gap-1" onClick={() => column.toggleSorting()}>
        Win rate
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ getValue }) => {
      const v = getValue<number | null>();
      if (v === null) {
        return <span className="text-xs text-muted-foreground">—</span>;
      }
      const pct = v * 100;
      return (
        <span
          className={cn(
            "font-mono-numbers text-xs",
            pct >= 60 ? "text-green-400" : pct >= 40 ? "text-foreground" : "text-red-400"
          )}
        >
          {pct.toFixed(0)}%
        </span>
      );
    },
    size: 80,
  },
  {
    accessorKey: "total_trades",
    header: ({ column }) => (
      <button className="flex items-center gap-1" onClick={() => column.toggleSorting()}>
        Trades
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs">{getValue<number>()}</span>
    ),
    size: 70,
  },
  {
    accessorKey: "tokens_traded",
    header: "Tokens",
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs">{getValue<number>()}</span>
    ),
    size: 70,
  },
  {
    accessorKey: "active_days",
    header: "Days",
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs">{getValue<number>()}</span>
    ),
    size: 60,
  },
  {
    accessorKey: "sustainability_score",
    header: ({ column }) => (
      <button className="flex items-center gap-1" onClick={() => column.toggleSorting()}>
        Sustainability
        <ArrowUpDown className="h-3 w-3" />
      </button>
    ),
    cell: ({ row }) => (
      <GradeCell
        score={row.original.sustainability_score}
        grade={row.original.sustainability_grade}
      />
    ),
    size: 110,
  },
  {
    accessorKey: "last_active",
    header: "Last active",
    cell: ({ getValue }) => (
      <span className="font-mono-numbers text-xs text-muted-foreground">
        {formatRelativeTime(getValue<string | null>())}
      </span>
    ),
    size: 90,
  },
];

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 10 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-md" />
      ))}
    </div>
  );
}

interface LeaderboardTableProps {
  data: WalletRow[];
  loading?: boolean;
  onRowClick?: (wallet: WalletRow) => void;
}

export function LeaderboardTable({ data, loading, onRowClick }: LeaderboardTableProps) {
  const [sorting, setSorting] = React.useState<SortingState>([
    { id: "rank", desc: false },
  ]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (loading) return <TableSkeleton />;

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="border-b border-border bg-surface">
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-3 py-2 text-left text-xs font-medium text-muted-foreground"
                  style={{ width: header.getSize() }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
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
                No qualifying wallets in this window yet.
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
