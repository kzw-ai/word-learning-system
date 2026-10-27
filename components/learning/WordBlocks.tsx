import React from 'react';
import { ChevronDown } from 'lucide-react';
import AudioPlayer from '@/components/AudioPlayer';
import CollocationText from '@/components/CollocationText';
import type { WordData } from '@/hooks/useWordData';

/**
 * 四个学习页（字 / 词 / 搭配 / 例句）共用的内容区块。
 *
 * 每页先突出「本步」的区块，前面步骤讲过的内容收进可展开的 RecapSection。
 * 此前四页各自复制同一套卡片，字学习页一次把拆字、词义、全部搭配、全部例句都
 * 摆出来，后面三页又各自重复其中一部分，学习者走五步看到的几乎是同一批内容。
 */

const SECTION_CARD = 'glass-card p-5 rounded-2xl border border-white/40';

export function WordHero({ word }: { word: WordData }) {
  return (
    <div className="flex flex-col items-center mb-2">
      <h2 className="text-[54px] font-extrabold text-gray-900 leading-none mb-2 mt-2">{word.hanzi}</h2>
      <div className="flex items-center gap-2 bg-indigo-50/80 px-4 py-1.5 rounded-full">
        <span className="text-sm font-medium text-indigo-700 tracking-widest">{word.pinyin}</span>
        <AudioPlayer text={word.hanzi} language="zh-CN" buttonSize="sm" />
      </div>
    </div>
  );
}

function SectionTitle({ zh, en }: { zh: string; en: string }) {
  return (
    <h3 className="text-sm font-bold text-indigo-700 tracking-wide mb-3">
      {zh} <span className="font-semibold text-indigo-700/80">{en}</span>
    </h3>
  );
}

export function CharacterBreakdown({ word }: { word: WordData }) {
  const characters = word.characters ?? [];
  return (
    <section>
      <SectionTitle zh="拆字" en="Characters" />
      {characters.length === 0 ? (
        <p className="text-sm text-gray-600">暂无拆字数据。</p>
      ) : (
        <div className="space-y-3">
          {characters.map((item, index) => (
            <div key={`${item.character}-${index}`} className={`flex items-center ${SECTION_CARD} !p-3`}>
              <span className="font-extrabold text-lg text-gray-800 shrink-0 w-8">{item.character}</span>
              <span className="text-sm font-semibold text-indigo-600 shrink-0 w-14 text-left">{item.pinyin}</span>
              <p className="text-sm text-gray-700 font-medium px-2 flex-1 leading-relaxed break-words">{item.definition}</p>
              <AudioPlayer text={item.character} language="zh-CN" buttonSize="sm" />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function DefinitionBlock({ word }: { word: WordData }) {
  return (
    <section>
      <SectionTitle zh="词义" en="Meaning" />
      <div className={SECTION_CARD}>
        <p className="text-lg text-gray-800 font-medium leading-relaxed">{word.definition || '暂无释义。'}</p>
      </div>
    </section>
  );
}

export function CollocationList({ word }: { word: WordData }) {
  const collocations = word.collocations ?? [];
  return (
    <section>
      <SectionTitle zh="搭配" en="Collocations" />
      {collocations.length === 0 ? (
        <p className="text-sm text-gray-600">这个词暂时没有搭配。</p>
      ) : (
        <div className={`${SECTION_CARD} space-y-4`}>
          {collocations.map((col, index) => (
            <div key={index} className="flex justify-between items-center">
              <div className="flex-1 pr-4">
                <div className="flex items-center gap-1.5 text-lg font-semibold text-gray-800 mb-1 flex-wrap">
                  <CollocationText text={col.collocation} target={word.hanzi || word.pinyin} />
                </div>
                <p className="text-base text-gray-600">{col.translation}</p>
              </div>
              <AudioPlayer
                text={col.collocation.replace(/（[^）]*）/g, '')}
                audioUrl={col.audio}
                language="zh-CN"
                buttonSize="sm"
              />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function ExampleList({ word, limit }: { word: WordData; limit?: number }) {
  const examples = (word.examples ?? []).slice(0, limit);
  return (
    <section>
      <SectionTitle zh="例句" en="Examples" />
      {examples.length === 0 ? (
        <p className="text-sm text-gray-600">这个词暂时没有例句，可以直接继续。</p>
      ) : (
        <div className={`${SECTION_CARD} space-y-6`}>
          {examples.map((ex, index) => (
            <div key={index} className="flex flex-col relative">
              <p className="text-lg font-semibold text-gray-800 leading-relaxed pr-10">{ex.sentence}</p>
              <div className="absolute top-0 right-0">
                <AudioPlayer text={ex.sentence} audioUrl={ex.audio} language="zh-CN" buttonSize="sm" />
              </div>
              {ex.pinyin && (
                <p className="text-base text-indigo-700 mt-2 font-medium tracking-wide leading-relaxed">{ex.pinyin}</p>
              )}
              <p className="text-base text-gray-600 mt-2 leading-relaxed">{ex.translation}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/**
 * 前面步骤的内容，默认折叠。用原生 details/summary，键盘和读屏都可用。
 * 从后面的步骤进入（VKS 自评跳级）的学习者也能在这里补看前面的内容。
 */
export function RecapSection({ labels, children }: { labels: string[]; children: React.ReactNode }) {
  return (
    <details className="group glass-card rounded-2xl border border-white/40">
      <summary className="flex items-center justify-between cursor-pointer list-none px-5 h-12 text-sm font-semibold text-gray-700 select-none [&::-webkit-details-marker]:hidden">
        <span>回顾：{labels.join(' · ')}</span>
        <ChevronDown size={18} className="transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="px-4 pb-5 space-y-5">{children}</div>
    </details>
  );
}
