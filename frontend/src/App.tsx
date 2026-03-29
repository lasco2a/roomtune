import { WizardProvider } from './hooks/useWizard';
import { WizardLayout } from './components/wizard';

export default function App() {
  return (
    <WizardProvider>
      <WizardLayout />
    </WizardProvider>
  );
}
