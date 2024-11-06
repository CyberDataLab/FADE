import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AnomalyDetectorComponent } from './anomaly-detector.component';

describe('AnomalyDetectorComponent', () => {
  let component: AnomalyDetectorComponent;
  let fixture: ComponentFixture<AnomalyDetectorComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AnomalyDetectorComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AnomalyDetectorComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
