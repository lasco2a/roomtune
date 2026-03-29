import { type WizardStep, WIZARD_STEPS } from '../../types';
import { CheckCircle2, Circle } from 'lucide-react';

interface WizardNavProps {
  currentStep: WizardStep;
  onStepClick: (step: WizardStep) => void;
  completedSteps: Set<WizardStep>;
}

export function WizardNav({ currentStep, onStepClick, completedSteps }: WizardNavProps) {
  return (
    <nav className="flex items-center gap-1 overflow-x-auto px-2 py-4">
      {WIZARD_STEPS.map((step, i) => {
        const isActive = currentStep === step.key;
        const isCompleted = completedSteps.has(step.key);
        const isPast = WIZARD_STEPS.findIndex((s) => s.key === currentStep) > i;

        return (
          <div key={step.key} className="flex items-center">
            <button
              onClick={() => onStepClick(step.key)}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors
                ${isActive ? 'bg-indigo-600/20 text-indigo-400' : ''}
                ${isCompleted ? 'text-emerald-400 hover:bg-emerald-600/10' : ''}
                ${!isActive && !isCompleted ? 'text-gray-500 hover:bg-gray-800/60 hover:text-gray-300' : ''}
              `}
            >
              {isCompleted ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <Circle
                  className={`h-4 w-4 ${isActive ? 'text-indigo-400' : 'text-gray-600'}`}
                />
              )}
              <span className="hidden sm:inline">{step.label}</span>
              <span className="sm:hidden">{step.number}</span>
            </button>

            {i < WIZARD_STEPS.length - 1 && (
              <div
                className={`mx-1 h-px w-6 ${
                  isPast || isCompleted ? 'bg-emerald-500/40' : 'bg-gray-700'
                }`}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
