"use client";

import React from "react";
import { FileText, Layers, AlignLeft, ShieldAlert } from "lucide-react";

interface MetricsProps {
  documentsCount: number;
  pagesCount: number;
  wordsCount: number;
  maxSizeMb: number;
}

export const MetricsCards: React.FC<MetricsProps> = ({
  documentsCount,
  pagesCount,
  wordsCount,
  maxSizeMb,
}) => {
  const cards = [
    {
      label: "Documents Processed",
      value: documentsCount.toLocaleString(),
      change: documentsCount > 0 ? "Active Session" : "Ready for uploads",
      icon: FileText,
      gradient: "from-blue-500/20 to-cyan-500/10",
      border: "border-blue-500/30",
      iconColor: "text-blue-400",
    },
    {
      label: "Pages Extracted",
      value: pagesCount.toLocaleString(),
      change: "Preserving page boundaries",
      icon: Layers,
      gradient: "from-indigo-500/20 to-purple-500/10",
      border: "border-indigo-500/30",
      iconColor: "text-indigo-400",
    },
    {
      label: "Words Extracted",
      value: wordsCount.toLocaleString(),
      change: "Clean normalized tokens",
      icon: AlignLeft,
      gradient: "from-emerald-500/20 to-teal-500/10",
      border: "border-emerald-500/30",
      iconColor: "text-emerald-400",
    },
    {
      label: "Security & Limits",
      value: `${maxSizeMb} MB`,
      change: "PDF, DOCX, TXT magic-bytes verified",
      icon: ShieldAlert,
      gradient: "from-amber-500/20 to-orange-500/10",
      border: "border-amber-500/30",
      iconColor: "text-amber-400",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            className={`relative overflow-hidden rounded-2xl bg-slate-900/60 p-5 border ${card.border} backdrop-blur-sm transition-all duration-300 hover:scale-[1.01] hover:shadow-lg`}
          >
            <div
              className={`absolute -right-4 -bottom-4 w-24 h-24 rounded-full bg-gradient-to-br ${card.gradient} blur-2xl pointer-events-none`}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 tracking-wide uppercase">
                {card.label}
              </span>
              <div className={`p-2 rounded-xl bg-slate-800/80 ${card.iconColor}`}>
                <Icon className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <p className="text-2xl font-bold text-white tracking-tight">
                {card.value}
              </p>
              <p className="text-[11px] text-slate-400 mt-1 font-medium">
                {card.change}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
