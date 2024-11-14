import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ImportScenarioComponent } from './import-scenario.component';

describe('ImportScenarioComponent', () => {
  let component: ImportScenarioComponent;
  let fixture: ComponentFixture<ImportScenarioComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ImportScenarioComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ImportScenarioComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
