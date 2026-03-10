import React from 'react';
import { Check } from 'lucide-react';

export function StepWizard({ steps, currentStep, onStepClick, locked = false }) {
  return (
    <div className="step-wizard">
      {steps.map((step, idx) => {
        const stepNum = idx + 1;
        const isCompleted = stepNum < currentStep;
        const isActive = stepNum === currentStep;
        const isClickable = stepNum < currentStep && !locked;
        return (
          <React.Fragment key={step.id}>
            <div
              className={`step-item ${isActive ? 'step-active' : ''} ${isCompleted ? 'step-completed' : ''} ${isClickable ? 'step-clickable' : ''}`}
              onClick={() => isClickable && onStepClick(stepNum)}
            >
              <div className="step-circle">
                {isCompleted ? <Check size={14} /> : stepNum}
              </div>
              <span className="step-label">{step.label}</span>
            </div>
            {idx < steps.length - 1 && <div className={`step-connector ${isCompleted ? 'step-connector-done' : ''}`} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}
