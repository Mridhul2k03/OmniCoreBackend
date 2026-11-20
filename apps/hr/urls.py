from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.hr.views import EmployeeInvitationAcceptView, EmployeeViewSet, LeaveRequestViewSet, SalaryStructureViewSet, PayrollViewSet

router = DefaultRouter()
router.register('employees', EmployeeViewSet, basename='employees')
router.register('leave-requests', LeaveRequestViewSet, basename='leave_requests')
router.register('salary-structures', SalaryStructureViewSet, basename='salary_structures')
router.register('payrolls', PayrollViewSet, basename='payrolls')

app_name = 'hr'

urlpatterns = [
    path('hr/invitations/accept/', EmployeeInvitationAcceptView.as_view(), name='employee_invitation_accept'),
    path('hr/', include(router.urls)),
]
