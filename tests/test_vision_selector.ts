"use strict";
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VisionProviderSelector } from '../../apps/desktop/src/components/VisionSelector';
import { api } from '../../apps/desktop/src/api/client';

// Mock del API
jest.mock('../../apps/desktop/src/api/client', () => {
  return {
    api: {
      health: jest.fn().mockResolvedValue({
        vision_provider: {
          configured: 'heuristic',
          remote_configured: false,
          available: ['heuristic', 'remote', 'auto'],
        },
      }),
    },
  };
});

describe('VisionProviderSelector', () => {
  beforeEach(() => {
    // Limpiar localStorage antes de cada test
    localStorage.clear();
  });

  it('debe mostrar el selector con el proveedor por defecto (heuristic)', async () => {
    render(<VisionProviderSelector />);

    // Esperar a que se cargue el componente
    await waitFor(() => {
      expect(screen.getByText('Local')).toBeInTheDocument();
      expect(screen.getByText('Local')).toHaveClass('active');
    });
  });

  it('debe cambiar el proveedor a "remote" y persistirlo en localStorage', async () => {
    render(<VisionProviderSelector />);

    // Esperar a que se cargue el componente
    await waitFor(() => {
      expect(screen.getByText('Local')).toBeInTheDocument();
    });

    // Hacer clic en "Remote"
    const remoteButton = screen.getByText('Remoto');
    fireEvent.click(remoteButton);

    // Verificar que el botón "Remote" está activo
    await waitFor(() => {
      expect(remoteButton).toHaveClass('active');
    });

    // Verificar que se guardó en localStorage
    expect(localStorage.getItem('uibinder.visionProvider')).toBe('remote');
  });

  it('debe cambiar el proveedor a "auto" y persistirlo en localStorage', async () => {
    render(<VisionProviderSelector />);

    // Esperar a que se cargue el componente
    await waitFor(() => {
      expect(screen.getByText('Local')).toBeInTheDocument();
    });

    // Hacer clic en "Auto"
    const autoButton = screen.getByText('Auto');
    fireEvent.click(autoButton);

    // Verificar que el botón "Auto" está activo
    await waitFor(() => {
      expect(autoButton).toHaveClass('active');
    });

    // Verificar que se guardó en localStorage
    expect(localStorage.getItem('uibinder.visionProvider')).toBe('auto');
  });

  it('debe deshabilitar el botón "Remote" si no está configurado', async () => {
    // Mockear que el proveedor remoto no está configurado
    (api.health as jest.Mock).mockResolvedValueOnce({
      vision_provider: {
        configured: 'heuristic',
        remote_configured: false,
        available: ['heuristic', 'remote', 'auto'],
      },
    });

    render(<VisionProviderSelector />);

    // Esperar a que se cargue el componente
    await waitFor(() => {
      expect(screen.getByText('Local')).toBeInTheDocument();
    });

    // Verificar que el botón "Remote" está deshabilitado
    const remoteButton = screen.getByText('Remoto');
    expect(remoteButton).toBeDisabled();
  });
});