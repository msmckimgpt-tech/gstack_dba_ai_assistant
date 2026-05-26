---
doc_type: WIKI_SOURCE_SUMMARY
scope: project
status: stub
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, source_summary]
ai_read_priority: 8
wiki_role: source_summary
wiki_name: project
confidence: medium
maturity: stub
ai_generated: true
title: "<Source Title>"
type: source
date: <YYYY-MM-DD>
source_file: ../raw/<path-relative-to-raw>
tags: []
---

# <Source Title>

> Source page template. Schema 출처: SamurAIGPT/llm-wiki-agent (2.7k stars, https://github.com/SamurAIGPT/llm-wiki-agent) 의 CLAUDE.md 의 "Source page format" 본문.

## 목차

1. [개요](#1-개요)
2. [핵심 주장 (Key Claims)](#2-핵심-주장-key-claims)
3. [핵심 인용 (Key Quotes)](#3-핵심-인용-key-quotes)
4. [연결 (Connections)](#4-연결-connections)
5. [충돌 (Contradictions)](#5-충돌-contradictions)
6. [Provenance](#6-provenance)
7. [관련 문서](#7-관련-문서)
8. [분류](#8-분류)

## 1. 개요

> 2~4 문장 summary. *Key Claims, Key Quotes, Connections, Contradictions* 를 *합성* 한 single paragraph.

(TBD)

## 2. 핵심 주장 (Key Claims)

> 글머리표 list. 각 claim 은 한 줄.

- (TBD)

## 3. 핵심 인용 (Key Quotes)

> 본문에서 직접 인용 + 문맥 1줄.

> "(인용 1)" — context

## 4. 연결 (Connections)

> 본 source 와 관련된 wiki 의 entity/concept 페이지에 wikilink.

- 인물/조직: [[../entities/<entity-slug>|<Entity Name>]]
- 개념: [[../concepts/<concept-slug>|<Concept Name>]]
- 다른 source: [[<other-source-slug>|<Other Source>]]
- ADR (있다면): [[../Decisions/<adr-id>|<ADR Title>]]

## 5. 충돌 (Contradictions)

> 본 source 와 다른 wiki 페이지가 *모순* 되는 부분. 발견 시 flag.

- 없음 (또는 (TBD): <conflict 1줄 + 어느 페이지와 충돌>)

## 6. Provenance

- **출처 분류**: `extracted` (원전에서 그대로) | `inferred` (AI 합성) | `ambiguous` (출처 모호)
- **신뢰도**: `high` | `medium` | `low` | `uncertain`
- **마지막 review**: <YYYY-MM-DD>

## 7. 관련 문서

- [[../raw/README|Raw sources 영역]]
- [[_Index|Sources MOC]]

## 8. 분류

`#wiki/source_summary` · `#confidence/medium` · `#maturity/stub`
