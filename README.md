# SaveMyGrade

SaveMyGrade is a project built to help SFU students discover courses that are more likely to be manageable and grade-friendly for their program goals.

## Problem

Choosing courses can feel like guesswork. Students often rely on scattered opinions, outdated advice, or word of mouth when trying to balance GPA and workload.

## Solution

SaveMyGrade combines student review signals and AI-assisted analysis to surface courses that appear easier to succeed in.

At a high level, the platform will:
- Collect professor review data from RateMyProfessors.
- Identify which courses those reviews refer to.
- Estimate course difficulty and effort level.
- Highlight classes that are likely to be lower effort with stronger grade outcomes.

## Core Features

- Course difficulty insights based on professor-linked review data.
- Class discovery for students who want GPA-friendly options.
- AI filtering of reviews into:
  - Low-effort signal
  - High-effort signal
- Program-focused course recommendations for SFU students.

## How AI Is Used

We use AI to classify review text quality and effort signals, helping separate reviews that suggest:
- a class is manageable with reasonable effort
- a class demands heavy workload or has high complexity

This improves recommendation quality by reducing noise in raw review data.

## Who It’s For

- SFU students planning future semesters
- Students optimizing for workload + GPA balance
- Students comparing multiple electives or program requirements

## Current Status

This project is in active development. The initial focus is:
- Data collection and cleaning
- Review-to-course mapping
- AI-based review classification
- Ranking logic for “easy class” recommendations

## Planned Roadmap

1. Build data ingestion pipeline for professor/course review sources.
2. Train/tune effort-classification model for review text.
3. Develop scoring system for course difficulty and grade-friendliness.
4. Build UI for searching and filtering by program.
5. Add transparency metrics so users can understand why a class is recommended.

## Disclaimer

SaveMyGrade provides guidance, not guarantees. Course experience varies by instructor, semester, and student learning style.

## Team

Built at Mountain Madness 2026.
