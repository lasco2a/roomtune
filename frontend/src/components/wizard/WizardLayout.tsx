import { useState, useCallback } from 'react';
import type { WizardStep } from '../../types';
import { WIZARD_STEPS } from '../../types';
import { WizardNav } from './WizardNav';
import { SetupStep } from './SetupStep';
import { ConnectionStep } from './ConnectionStep';
import { MeasurementStep } from './MeasurementStep';
import { AnalysisStep } from './AnalysisStep';
import { TargetStep } from './TargetStep';
import { ApplyEQStep } from './ApplyEQStep';
import { VerificationStep } from './VerificationStep';
import { Button } from '../ui';

export function WizardLayout() {
  const [currentStep, setCurrentStep] = useState<WizardStep>('setup');
  const [completedSteps, setCompletedSteps] = useState<Set<WizardStep>>(new Set());

  const markComplete = useCallback((step: WizardStep) => {
    setCompletedSteps((prev) => new Set([...prev, step]));
  }, []);

  const goNext = useCallback(() => {
    const idx = WIZARD_STEPS.findIndex((s) => s.key === currentStep);
    if (idx < WIZARD_STEPS.length - 1) {
      markComplete(currentStep);
      setCurrentStep(WIZARD_STEPS[idx + 1].key);
    }
  }, [currentStep, markComplete]);

  const goPrev = useCallback(() => {
    const idx = WIZARD_STEPS.findIndex((s) => s.key === currentStep);
    if (idx > 0) {
      setCurrentStep(WIZARD_STEPS[idx - 1].key);
    }
  }, [currentStep]);

  /** Navigate to a step via the top nav — only allow completed or current steps. */
  const handleStepClick = useCallback(
    (step: WizardStep) => {
      const targetIdx = WIZARD_STEPS.findIndex((s) => s.key === step);
      const currentIdx = WIZARD_STEPS.findIndex((s) => s.key === currentStep);
      // Allow clicking completed steps or the current step
      if (targetIdx <= currentIdx || completedSteps.has(step)) {
        setCurrentStep(step);
      }
    },
    [currentStep, completedSteps],
  );

  const currentIndex = WIZARD_STEPS.findIndex((s) => s.key === currentStep);
  const isFirst = currentIndex === 0;

  const stepComponent = () => {
    switch (currentStep) {
      case 'setup':
        return <SetupStep onComplete={goNext} />;
      case 'connection':
        return <ConnectionStep onComplete={goNext} />;
      case 'measurement':
        return <MeasurementStep onComplete={goNext} />;
      case 'analysis':
        return <AnalysisStep onComplete={goNext} />;
      case 'target':
        return <TargetStep onComplete={goNext} />;
      case 'apply':
        return <ApplyEQStep onComplete={goNext} />;
      case 'verification':
        return <VerificationStep />;
    }
  };

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-800 px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            RT
          </div>
          <h1 className="text-lg font-semibold text-gray-100">RoomTune</h1>
        </div>
        <span className="text-xs text-gray-500">v0.1.0</span>
      </header>

      {/* Step navigation */}
      <div className="border-b border-gray-800">
        <WizardNav
          currentStep={currentStep}
          onStepClick={handleStepClick}
          completedSteps={completedSteps}
        />
      </div>

      {/* Step content */}
      <main className="flex-1 overflow-y-auto p-6">{stepComponent()}</main>

      {/* Footer — Back button only; each step has its own Continue button */}
      <footer className="flex items-center justify-between border-t border-gray-800 px-6 py-3">
        <Button variant="ghost" onClick={goPrev} disabled={isFirst}>
          Back
        </Button>
        <span className="text-xs text-gray-500">
          Step {currentIndex + 1} of {WIZARD_STEPS.length}
        </span>
        <div className="w-20" /> {/* Spacer to keep footer centered */}
      </footer>
    </div>
  );
}
